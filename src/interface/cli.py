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
                print("[CLI] /peers [* | namespace] /conn /rtt /reconnect /games /create /start /cancel /join /leave /guess /word /status /log <nível> /quit")
            elif command == "/peers":
                namespace = args[0] if args else ""
                peers = self.app.listar_peers(namespace)
                if not peers:
                    print("[CLI] nenhum peer conhecido")
                for peer in peers:
                    print(
                        f"[CLI] {peer['peer_id']} "
                        f"status={peer['status']} "
                        f"{peer['ip'] or '-'}:{peer['port'] or '-'}"
                    )
            elif command == "/conn":
                conexoes = self.app.listar_conexoes()
                if not conexoes:
                    print("[CLI] nenhuma conexão ativa")
                for conexao in conexoes:
                    rtt = "-" if conexao["rtt"] is None else f"{conexao['rtt'] * 1000:.1f} ms"
                    print(
                        f"[CLI] {conexao['peer_id']} "
                        f"dir={conexao['direcao']} status={conexao['status']} rtt={rtt}"
                    )
            elif command == "/rtt":
                medidas = self.app.listar_rtt()
                if not medidas:
                    print("[CLI] RTT indisponível")
                for medida in medidas:
                    print(f"[CLI] {medida['peer_id']} RTT={medida['rtt'] * 1000:.1f} ms")
            elif command == "/reconnect":
                ok, resultado = self.app.reconectar()
                if not ok:
                    print(f"[CLI] {resultado}")
                else:
                    print(
                        "[CLI] reconciliação concluída "
                        f"(conectar={resultado['conectar']} fechar={resultado['fechar']} "
                        f"peers={resultado['peers']})"
                    )
            elif command == "/log" and args:
                ok, resultado = self.app.definir_log_level(args[0])
                print(f"[CLI] nível de log: {resultado}" if ok else f"[CLI] {resultado}")
            elif command == "/log":
                print("[CLI] uso: /log <DEBUG|INFO|WARNING|ERROR>")
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