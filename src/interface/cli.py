import shlex
import threading


class CLI:
    def __init__(self, app, encerrar):
        self.app = app
        self.encerrar = encerrar

    def run(self):
        print("[CLI] /help para listar comandos")
        while not self.encerrar.is_set():
            try:
                raw = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.encerrar.set()
                break
            if not raw:
                continue
            if not raw.startswith("/"):
                print("[CLI] comandos começam com /")
                continue
            try:
                parts = shlex.split(raw)
            except ValueError as exc:
                print(f"[CLI] comando inválido: {exc}")
                continue
            command = parts[0].lower()
            args = parts[1:]

            if command == "/help":
                print("[CLI] /peers /conn /rtt /reconnect /games /create /start /cancel /join /leave /guess /word /status /log /quit")
            elif command == "/games":
                print("[CLI] buscando partidas...")
                for peer_id, games in self.app.listar_partidas().items():
                    print(f"[CLI] {peer_id}: {games}")
            elif command == "/create":
                if not args:
                    print("[CLI] uso: /create <palavra> [max_players]")
                elif args[0] == "--random":
                    ok, result = self.app.criar(random_word=True, max_players=args[1] if len(args) > 1 else None)
                    print(f"[Host] partida criada: {result}" if ok else f"[CLI] {result}")
                else:
                    ok, result = self.app.criar(args[0], args[1] if len(args) > 1 else None)
                    print(f"[Host] partida criada: {result}" if ok else f"[CLI] {result}")
            elif command == "/start":
                ok, result = self.app.iniciar()
                print(result if ok else f"[CLI] {result}")
            elif command == "/cancel":
                print("[Host] partida cancelada" if self.app.cancelar() else "[CLI] nenhuma partida hospedada")
            elif command == "/join" and args:
                ok, result = self.app.entrar(args[0])
                print("[Game] entrada confirmada" if ok else f"[CLI] entrada recusada: {result}")
            elif command == "/leave":
                print("[Game] partida abandonada" if self.app.sair() else "[CLI] não participa de partida")
            elif command == "/guess" and args:
                ok, result = self.app.guess(letter=args[0])
                print(result)
            elif command == "/word" and args:
                ok, result = self.app.guess(word=args[0])
                print(result)
            elif command == "/status":
                print(self.app.status())
            elif command == "/quit":
                self.app.cancelar() if self.app.host is not None else self.app.sair()
                self.encerrar.set()
                break
            else:
                print(f"[CLI] comando não implementado ou inválido: {command}")