import json
import socket
import threading
from collections.abc import Callable, Iterable

MAX_LINE_LENGTH = 32768
MessageHandler = Callable[[dict], Iterable[dict] | dict | None]


class JsonLineConnection:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buffer = b""
        self._send_lock = threading.Lock()

    def send(self, message: dict) -> None:
        payload = (json.dumps(message, ensure_ascii=True) + "\n").encode("utf-8")
        with self._send_lock:
            self.sock.sendall(payload)

    def receive(self) -> dict | None:
        while b"\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                if not self._buffer:
                    return None
                raise ConnectionError("Conexão encerrada no meio de uma mensagem")

            self._buffer += chunk
            if len(self._buffer) > MAX_LINE_LENGTH:
                raise ValueError("Mensagem maior que o limite permitido")

        line, self._buffer = self._buffer.split(b"\n", 1)
        if not line.strip():
            raise ValueError("Mensagem vazia")

        mensagem = json.loads(line.decode("utf-8"))
        if not isinstance(mensagem, dict):
            raise ValueError("A mensagem JSON deve ser um objeto")
        return mensagem

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class TcpPeerServer:
    def __init__(
        self,
        host: str,
        port: int,
        on_message: MessageHandler,
    ):
        self.host = host
        self.port = port
        self.on_message = on_message
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._clients: list[JsonLineConnection] = []
        self._clients_lock = threading.Lock()

    @property
    def address(self) -> tuple[str, int]:
        if self._listener is None:
            raise RuntimeError("Servidor ainda não foi iniciado")
        return self._listener.getsockname()

    def start(self) -> None:
        if self._listener is not None:
            raise RuntimeError("Servidor já está iniciado")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.listen()
        self._listener = listener
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        if self._listener is None:
            return

        while True:
            try:
                sock, _ = self._listener.accept()
            except OSError:
                return

            connection = JsonLineConnection(sock)
            with self._clients_lock:
                self._clients.append(connection)
            threading.Thread(
                target=self._client_loop,
                args=(connection,),
                daemon=True,
            ).start()

    def _client_loop(self, connection: JsonLineConnection) -> None:
        try:
            while True:
                message = connection.receive()
                if message is None:
                    return

                responses = self.on_message(message)
                if isinstance(responses, dict):
                    responses = [responses]
                if responses is not None:
                    for response in responses:
                        connection.send(response)
        except (ConnectionError, OSError, ValueError, json.JSONDecodeError):
            return
        finally:
            with self._clients_lock:
                if connection in self._clients:
                    self._clients.remove(connection)
            connection.close()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.close()
            self._listener = None

        with self._clients_lock:
            clients = self._clients.copy()
            self._clients.clear()
        for connection in clients:
            connection.close()


class TcpPeerClient:
    def __init__(self, on_message: Callable[[dict], None]):
        self.on_message = on_message
        self.connection: JsonLineConnection | None = None
        self._thread: threading.Thread | None = None

    def connect(self, host: str, port: int) -> None:
        if self.connection is not None:
            raise RuntimeError("Cliente já está conectado")

        sock = socket.create_connection((host, port), timeout=5)
        sock.settimeout(None)
        self.connection = JsonLineConnection(sock)
        self._thread = threading.Thread(
            target=self._receive_loop,
            daemon=True,
        )
        self._thread.start()

    def _receive_loop(self) -> None:
        if self.connection is None:
            return

        try:
            while True:
                message = self.connection.receive()
                if message is None:
                    return
                self.on_message(message)
        except (ConnectionError, OSError, ValueError, json.JSONDecodeError):
            return

    def send(self, message: dict) -> None:
        if self.connection is None:
            raise RuntimeError("Cliente não está conectado")
        self.connection.send(message)

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
