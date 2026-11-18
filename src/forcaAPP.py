import logging
import random
import threading
import time
from pathlib import Path


    
from conections.peer_connection import enviar_para_peer
from conections.protocolo import criar_envelope
from game.game_host import GameHost
from game.game_player import GamePlayer


logger = logging.getLogger(__name__)


class P2PForcaApp:
    def __init__(self, config, tabela):
        self.config = config
        self.tabela = tabela
        self.peer_id = f"{config['name']}@{config['namespace']}"
        self.host = None
        self.player = None
        self.lock = threading.Lock()
        self.pending = {}
        self.games_by_host = {}

    def enviar(self, peer_id, message):
        return enviar_para_peer(self.tabela, peer_id, message)

    def listar_peers(self, namespace=""):
        peers = []
        namespace = namespace.strip().lower() if namespace else ""
        for peer in self.tabela.listar():
            peer_id = peer["peer_id"]
            if namespace and namespace != "*" and not peer_id.endswith("@" + namespace.upper()):
                continue
            peers.append({
                "peer_id": peer_id,
                "status": peer["status"].value if hasattr(peer["status"], "value") else str(peer["status"]),
                "ip": peer.get("ip"),
                "port": peer.get("port"),
                "rtt": peer.get("rtt"),
            })
        return peers

    def listar_conexoes(self):
        conexoes = []
        for peer_id, peer in ((peer["peer_id"], peer) for peer in self.tabela.listar()):
            conexao = peer.get("conexao")
            if conexao is not None:
                conexoes.append({
                    "peer_id": peer_id,
                    "status": peer["status"].value if hasattr(peer["status"], "value") else str(peer["status"]),
                    "direcao": peer.get("direcao"),
                    "rtt": peer.get("rtt"),
                })
        return conexoes

    def listar_rtt(self):
        return [
            {"peer_id": peer["peer_id"], "rtt": peer.get("rtt")}
            for peer in self.tabela.listar()
            if peer.get("rtt") is not None
        ]

    def reconectar(self):
        from conections.rendezvous_connection import discover
        from conections.peer_connection import conectar_e_registrar, encerrar_conexao

        lista = discover(self.config)
        if lista is None:
            return False, "falha ao consultar o Rendezvous"
        conectar, fechar = self.tabela.reconciliar(lista)
        for peer_id, conexao in fechar:
            threading.Thread(
                target=encerrar_conexao,
                args=(conexao, self.config, peer_id, "gone"),
                daemon=True,
            ).start()
        for peer_id, ip, porta in conectar:
            threading.Thread(
                target=conectar_e_registrar,
                args=(peer_id, ip, porta, self.config, self.tabela, self.handler),
                daemon=True,
            ).start()
        return True, {"conectar": len(conectar), "fechar": len(fechar), "peers": len(self.tabela.listar())}

    def definir_log_level(self, nivel):
        niveis = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        nivel = nivel.upper()
        if nivel not in niveis:
            return False, "nível inválido; use DEBUG, INFO, WARNING ou ERROR"
        logging.getLogger().setLevel(niveis[nivel])
        return True, nivel

    def encerramento_limpo(self):
        if self.host is not None:
            return self.cancelar()
        if self.player is not None:
            return self.sair()
        return True

    def broadcast(self, message_type, message_fields):
        if self.host is None:
            return
        for player_id in list(self.host.jogadores):
            message = criar_envelope(
                message_type,
                src=self.peer_id,
                dst=player_id,
                game_id=self.host.game_id,
                **message_fields,
            )
            try:
                self.enviar(player_id, message)
            except Exception:
                logger.warning("Falha ao enviar %s para %s", message_type, player_id)

    def criar(self, palavra=None, max_players=None, random_word=False):
        if self.host is not None or self.player is not None:
            return False, "uma partida já está ativa"
        if random_word:
            words_path = Path(self.config.get("words_file", "words.txt"))
            if not words_path.is_absolute():
                words_path = Path(__file__).resolve().parents[1] / words_path
            try:
                palavras = [
                    linha.strip() for linha in words_path.read_text(encoding="utf-8").splitlines()
                    if linha.strip()
                ]
                if not palavras:
                    raise ValueError("arquivo de palavras vazio")
                palavra = random.choice(palavras)
            except Exception as exc:
                return False, f"não foi possível sortear palavra: {exc}"

        try:
            self.host = GameHost(
                self.peer_id,
                palavra,
                vidas=int(self.config.get("lives", 6)),
                max_jogadores=int(max_players or self.config.get("max_players", 4)),
                turn_timeout=int(self.config.get("turn_timeout", 30)),
            )
            return True, self.host.game_id
        except ValueError as exc:
            self.host = None
            return False, str(exc)

    def cancelar(self):
        if self.host is None:
            return False
        if self.host.estado in ("RUNNING", "OPEN"):
            game_over = self._game_over("ABORTED", reason="no_players" if not self.host.jogadores else "host_shutdown")
            for player_id in list(self.host.jogadores):
                try:
                    self.enviar(player_id, game_over(player_id))
                except Exception:
                    pass
        self.host = None
        return True

    def iniciar(self):
        if self.host is None:
            return False, "nenhuma partida hospedada"
        if not self.host.iniciar():
            return False, "é necessário pelo menos um jogador"
        for player_id in list(self.host.jogadores):
            try:
                self.enviar(player_id, self.host.game_start(player_id))
                self.enviar(player_id, self.host.state(player_id))
            except Exception as exc:
                logger.warning("Falha ao iniciar jogo para %s: %s", player_id, exc)
        threading.Thread(target=self._turn_timeout_loop, daemon=True).start()
        return True, self.host.game_id

    def _turn_timeout_loop(self):
        host = self.host
        if host is None:
            return
        while host.esta_em_andamento() and host is self.host:
            state = host.processar_timeout()
            if state is not None:
                for player_id in list(host.jogadores):
                    state_copy = dict(state)
                    state_copy["dst"] = player_id
                    state_copy["msg_id"] = criar_envelope("STATE")["msg_id"]
                    try:
                        self.enviar(player_id, state_copy)
                    except Exception:
                        pass
            time.sleep(0.5)

    def listar_partidas(self, timeout=1.0):
        deadline = time.monotonic() + min(timeout, 2.0)
        while time.monotonic() < deadline:
            peers = [
                peer_id
                for peer_id in self.tabela.peers
                if self.tabela.obter(peer_id, "conexao") is not None
            ]
            if peers:
                break
            time.sleep(0.05)

        peers = [peer_id for peer_id in self.tabela.peers if self.tabela.obter(peer_id, "conexao") is not None]
        resposta = {}
        for peer_id in peers:
            event = threading.Event()
            token = criar_envelope("GAME_LIST")["msg_id"]
            self.pending[token] = (event, peer_id, [])
            message = criar_envelope("GAME_LIST", src=self.peer_id, dst=peer_id, msg_id=token)
            try:
                self.enviar(peer_id, message)
            except Exception:
                continue
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.05)
        for peer_id in peers:
            for token, (event, owner, games) in list(self.pending.items()):
                if owner == peer_id:
                    if peer_id not in resposta:
                        resposta[peer_id] = games
                    self.pending.pop(token, None)
        self.games_by_host = {
            game["host"]: game
            for games in resposta.values()
            for game in games
        }
        return resposta

    def entrar(self, host_id, timeout=2.0):
        if self.host is not None or self.player is not None:
            return False, "já participa de uma partida"
        event = threading.Event()
        token = criar_envelope("JOIN")["msg_id"]
        response = {}
        self.pending[token] = (event, host_id, response)
        game = self.games_by_host.get(host_id)
        if game is None:
            self.pending.pop(token, None)
            return False, "execute /games antes de entrar"
        game_id = game["game_id"]
        message = criar_envelope(
            "JOIN",
            src=self.peer_id,
            dst=host_id,
            msg_id=token,
            game_id=game_id,
        )
        try:
            self.enviar(host_id, message)
        except Exception as exc:
            self.pending.pop(token, None)
            return False, str(exc)
        event.wait(timeout)
        self.pending.pop(token, None)
        if not event.is_set():
            return False, "timeout"
        return True if response.get("status") == "OK" else False, response

    def sair(self):
        if self.player is not None:
            host_id = self.player.host_id
        elif self.host is not None:
            return self.cancelar()
        else:
            return False
        message = criar_envelope(
            "LEAVE",
            src=self.peer_id,
            dst=host_id,
            game_id=self.player.game_id,
        )
        try:
            self.enviar(host_id, message)
        except Exception:
            pass
        self.player = None
        return True

    def guess(self, letter=None, word=None):
        if self.player is None:
            return False, "não está em uma partida"
        fields = {"letter": letter} if letter is not None else {"word": word}
        message = criar_envelope(
            "GUESS",
            src=self.peer_id,
            dst=self.player.host_id,
            game_id=self.player.game_id,
            **fields,
        )
        event = threading.Event()
        response = {}
        self.pending[message["msg_id"]] = (event, self.player.host_id, response)
        try:
            self.enviar(self.player.host_id, message)
        except Exception as exc:
            return False, str(exc)
        event.wait(2)
        self.pending.pop(message["msg_id"], None)
        return event.is_set(), response

    def status(self):
        if self.host is not None:
            host = self.host
            return (
                f"[Game] {host.game_id} (host: {self.peer_id}) status: {host.estado}\n"
                f"[Game] Palavra: {' '.join(host.jogo.mascara()) if host.esta_em_andamento() else '-' * len(host.jogo.palavra)} "
                f"Vidas: {host.jogo.vidas}/{self.config.get('lives', 6)}"
                f" Jogadores: {', '.join(host.jogadores)}"
            )
        if self.player is not None:
            return (
                f"[Game] {self.player.game_id} (host: {self.player.host_id}) status: {self.player.status}\n"
                f"[Game] Palavra: {' '.join(self.player.masked)} Vidas: {self.player.lives}"
                f" Jogadores: {', '.join(self.player.players)}"
                f" Vez de: {self.player.turn}"
            )
        return "[Game] no active game"

    def _game_over(self, result, reason=None):
        if self.host is None:
            return lambda _peer: None

        def make(peer_id):
            fields = {
                "result": result,
                "word": self.host.jogo.palavra,
                "winner": None,
                "scores": self.host.scores.copy(),
            }
            if reason:
                fields["reason"] = reason
            return criar_envelope(
                "GAME_OVER",
                src=self.peer_id,
                dst=peer_id,
                game_id=self.host.game_id,
                **fields,
            )
        return make

    def handler(self, message, peer_id, config, tabela):
        type_name = message.get("type")

        if type_name == "PEER_DOWN":
            if self.host is not None and peer_id in self.host.jogadores:
                self.host.remover_jogador(peer_id)
                if not self.host.jogadores:
                    self.host = None
                else:
                    for player_id in list(self.host.jogadores):
                        try:
                            self.enviar(player_id, self.host.state(player_id))
                        except Exception:
                            pass
            if self.player is not None and peer_id == self.player.host_id:
                logger.info("[Player] Host %s unreachable — game aborted", peer_id)
                self.player = None
            return

        if type_name == "GAME_LIST":
            games = []
            if self.host is not None:
                games.append({
                    "game_id": self.host.game_id,
                    "host": self.peer_id,
                    "status": self.host.estado,
                    "players": self.host.jogadores.copy(),
                    "max_players": self.host.max_jogadores,
                    "lives": self.host.jogo.vidas,
                    "word_length": len(self.host.jogo.palavra),
                })
            response = criar_envelope(
                "GAME_LIST_OK",
                src=self.peer_id,
                dst=peer_id,
                msg_id=message.get("msg_id"),
                games=games,
            )
            self.enviar(peer_id, response)
            return

        if type_name == "GAME_LIST_OK":
            for token, (event, owner, response) in list(self.pending.items()):
                if owner == peer_id:
                    response.extend(message.get("games", []))
                    event.set()
            return

        if type_name == "JOIN":
            if self.host is None:
                reason = "unknown_game"
            elif message.get("game_id") != self.host.game_id:
                reason = "unknown_game"
            elif self.host.estado == "FINISHED":
                reason = "game_finished"
            elif self.host.estado == "RUNNING":
                reason = "already_joined" if peer_id in self.host.jogadores else "game_running"
                if reason == "already_joined":
                    response = criar_envelope(
                        "JOIN_OK", src=self.peer_id, dst=peer_id,
                        msg_id=message.get("msg_id"), game_id=self.host.game_id,
                        players=self.host.jogadores.copy(), rejoin=True,
                    )
                    self.enviar(peer_id, response)
                    self.enviar(peer_id, self.host.state(peer_id))
                    return
            elif len(self.host.jogadores) >= self.host.max_jogadores:
                reason = "game_full"
            else:
                if not self.host.adicionar_jogador(peer_id):
                    reason = "game_full"
                else:
                    response = criar_envelope(
                        "JOIN_OK", src=self.peer_id, dst=peer_id,
                        msg_id=message.get("msg_id"), game_id=self.host.game_id,
                        players=self.host.jogadores.copy(), rejoin=False,
                    )
                    self.enviar(peer_id, response)
                    return
            response = criar_envelope(
                "JOIN_ERR", src=self.peer_id, dst=peer_id,
                msg_id=message.get("msg_id"), game_id=message.get("game_id"),
                reason=reason,
            )
            self.enviar(peer_id, response)
            return

        if type_name == "JOIN_OK":
            for token, (event, owner, response) in list(self.pending.items()):
                if owner == peer_id:
                    response.update(status="OK", message=message)
                    event.set()
            if self.player is None:
                self.player = GamePlayer(
                    self.peer_id,
                    message["game_id"],
                    peer_id,
                    word_hash="",
                    word_length=0,
                    lives=int(self.config.get("lives", 6)),
                    players=message["players"],
                )
            return

        if type_name == "JOIN_ERR":
            for token, (event, owner, response) in list(self.pending.items()):
                if owner == peer_id:
                    response.update(status="ERR", reason=message.get("reason"))
                    event.set()
            return

        if type_name == "LEAVE":
            if self.host is not None:
                removed = self.host.remover_jogador(peer_id)
                if removed:
                    response = criar_envelope(
                        "LEAVE_OK", src=self.peer_id, dst=peer_id,
                        msg_id=message.get("msg_id"), game_id=self.host.game_id,
                    )
                    self.enviar(peer_id, response)
                    if self.host.esta_em_andamento():
                        for player_id in list(self.host.jogadores):
                            self.enviar(player_id, self.host.state(player_id))
            return

        if type_name == "GAME_START":
            if self.player is None:
                self.player = GamePlayer(
                    self.peer_id,
                    message["game_id"],
                    peer_id,
                    message["word_hash"],
                    message["word_length"],
                    message["lives"],
                    message["players"],
                )
            self.player.status = "PLAYING"
            return

        if type_name == "STATE":
            if self.player is not None:
                self.player.processar_state(message)
            return

        if type_name == "GUESS":
            if self.host is None:
                return
            result = self.host.processar_guess(
                jogador=peer_id,
                letra=message.get("letter"),
                palavra=message.get("word"),
                msg_id=message.get("msg_id"),
            )
            try:
                self.enviar(peer_id, {k: v for k, v in result.items() if k not in ("state", "game_over")})
            except Exception:
                pass
            if "state" in result:
                for player_id in list(self.host.jogadores):
                    self.enviar(player_id, result["state"] | {"dst": player_id, "msg_id": criar_envelope("STATE")["msg_id"]})
            if "game_over" in result:
                for player_id in list(self.host.jogadores):
                    self.enviar(player_id, result["game_over"] | {"dst": player_id, "msg_id": criar_envelope("GAME_OVER")["msg_id"]})
            return

        if type_name == "GUESS_RESULT":
            for token, (event, owner, response) in list(self.pending.items()):
                if owner == peer_id:
                    response.update(message)
                    event.set()
            if self.player is not None:
                self.player.processar_guess_result(message)
            return

        if type_name == "GAME_OVER":
            if self.player is not None:
                self.player.processar_game_over(message)
            logger.info("[Player] GAME_OVER %s", message.get("result"))
            self.player = None
