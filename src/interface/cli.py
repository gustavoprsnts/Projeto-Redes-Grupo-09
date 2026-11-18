import shlex

AJUDA = """Comandos:
  /peers [* | #namespace]            descobre e lista peers (padrão: namespace local)
  /conn                              lista conexões ativas (direção, estado, RTT)
  /rtt                               RTT médio por peer
  /reconnect                         força reconciliação imediata com o Rendezvous
  /games                             pergunta aos vizinhos quais partidas existem
  /create <palavra> [max_players]    cria uma partida (você vira o host)
  /create --random [max_players]     cria partida com palavra sorteada do words.txt
  /start                             inicia a partida hospedada (exige >= 1 jogador)
  /cancel                            cancela a partida hospedada
  /join <host_peer_id>               entra na partida do host (ex.: /join alice@CIC)
  /leave                             sai da partida atual
  /guess <letra>                     palpite de letra
  /word <palavra>                    palpite da palavra inteira
  /status                            estado local da partida
  /log <DEBUG|INFO|WARNING|ERROR>    nível de log na tela
  /help                              esta ajuda
  /quit                              encerra (LEAVE/GAME_OVER, BYE e UNREGISTER)"""

class CLI:
    def __init__(self, app, *args):
        self.app = app
       
        if len(args) == 1:
            self.encerrar = args[0]
        elif len(args) >= 3:
            self.encerrar = args[2]
        else:
            self.encerrar = args[-1] if args else None

    def run(self):
        print("[CLI] /help para listar comandos")
        while self.encerrar is not None and not self.encerrar.is_set():
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

            try:
                if command == "/help":
                    print(AJUDA)

                elif command == "/peers":
                    namespace = args[0] if args else ""
                    peers = self.app.listar_peers(namespace)
                    if not peers:
                        print("[CLI] nenhum peer conhecido")
                    for peer in peers:
                        print(
                            f"[CLI] {peer['peer_id']} "
                            f"status={peer.get('status')} "
                            f"{peer.get('ip') or '-'}:{peer.get('port') or '-'}"
                        )

                elif command == "/conn":
                    conexoes = self.app.listar_conexoes()
                    if not conexoes:
                        print("[CLI] nenhuma conexão ativa")
                    for conexao in conexoes:
                        rtt = conexao.get("rtt")
                        rtt_txt = "-" if rtt is None else f"{rtt * 1000:.1f} ms"
                        print(
                            f"[CLI] {conexao.get('peer_id')} "
                            f"dir={conexao.get('direcao')} status={conexao.get('status')} rtt={rtt_txt}"
                        )

                elif command == "/rtt":
                    medidas = self.app.listar_rtt()
                    if not medidas:
                        print("[CLI] RTT indisponível")
                    for medida in medidas:
                        rtt = medida.get("rtt")
                        rtt_txt = "-" if rtt is None else f"{rtt * 1000:.1f} ms"
                        print(f"[CLI] {medida.get('peer_id')} RTT={rtt_txt}")

                elif command == "/reconnect":
                    ok, resultado = self.app.reconectar()
                    if not ok:
                        print(f"[CLI] {resultado}")
                    else:
                        print(
                            "[CLI] reconciliação concluída "
                            f"(conectar={resultado.get('conectar')} fechar={resultado.get('fechar')} "
                            f"peers={resultado.get('peers')})"
                        )

                elif command == "/log":
                    if not args:
                        print("[CLI] uso: /log <DEBUG|INFO|WARNING|ERROR>")
                    else:
                        ok, resultado = self.app.definir_log_level(args[0])
                        print(f"[CLI] nível de log: {resultado}" if ok else f"[CLI] {resultado}")

                elif command == "/games":
                    print("[CLI] buscando partidas...")
                    jogos = self.app.listar_partidas()
                    if not jogos:
                        print("[CLI] nenhuma partida encontrada")
                    else:
                        for peer_id, games in jogos.items():
                            print(f"[CLI] {peer_id}: {games}")

                elif command == "/create":
                    if not args:
                        print("[CLI] uso: /create <palavra> [max_players] | /create --random [max_players]")
                    else:
                        max_p = None
                        if len(args) > 1:
                            try:
                                max_p = int(args[1])
                            except ValueError:
                                print("[CLI] max_players deve ser um número inteiro")
                                continue
                        if args[0] == "--random":
                            ok, result = self.app.criar(random_word=True, max_players=max_p)
                        else:
                            ok, result = self.app.criar(args[0], max_p)
                        print(f"[Host] partida criada: {result}" if ok else f"[CLI] {result}")

                elif command == "/start":
                    ok, result = self.app.iniciar()
                    print(f"[Host] partida iniciada: {result}" if ok else f"[CLI] {result}")

                elif command == "/cancel":
                    print("[Host] partida cancelada" if self.app.cancelar() else "[CLI] nenhuma partida hospedada")

                elif command == "/join":
                    if not args:
                        print("[CLI] uso: /join <host_peer_id>")
                    else:
                        ok, result = self.app.entrar(args[0])
                        print("[Game] entrada confirmada" if ok else f"[CLI] entrada recusada: {result}")

                elif command == "/leave":
                    print("[Game] partida abandonada" if self.app.sair() else "[CLI] não participa de partida")

                elif command == "/guess":
                    if not args:
                        print("[CLI] uso: /guess <letra>")
                    else:
                        ok, result = self.app.guess(letter=args[0])
                        print(result if ok else f"[CLI] {result}")

                elif command == "/word":
                    if not args:
                        print("[CLI] uso: /word <palavra>")
                    else:
                        ok, result = self.app.guess(word=args[0])
                        print(result if ok else f"[CLI] {result}")

                elif command == "/status":
                    print(self.app.status())

                elif command == "/quit":
                    try:
                        if getattr(self.app, "host", None) is not None:
                            self.app.cancelar()
                        elif getattr(self.app, "player", None) is not None:
                            self.app.sair()
                    except Exception as exc:
                        print(f"[CLI] erro ao encerrar partida: {exc}")
                    self.encerrar.set()
                    break

                else:
                    print(f"[CLI] comando inválido: {command}")

            except Exception as exc:
                print(f"[CLI] erro ao executar {command}: {exc}")