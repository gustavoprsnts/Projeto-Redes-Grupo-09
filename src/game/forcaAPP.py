import logging
import math
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
    #funcao que inicializa a integraçao do p2p e seus atributos de controle 
    def __init__(self, config, tabela):
        self.config = config
        self.tabela = tabela
        self.peer_id = f"{config['name']}@{config['namespace']}"
        self.host = None
        self.player = None
        self.lock = threading.Lock()
        self.pending = {}
        self.games_by_host = {}

 # funcao para envio de mensagem para um peer especifico 
    def enviar(self, peer_id, message):
        return enviar_para_peer(self.tabela, peer_id, message)
    
 #funcao que processa respostas esperadas e libera threads aguardando retorno
    def resolver_pendente(self, message, peer_id):
        token = message.get("msg_id")
        pendente = self.pending.get(token)

        if pendente is None:
            return False

        event, owner, response = pendente

        if owner != peer_id:
            return False
        if message["type"] == "GAME_LIST_OK":
            
            response.extend(message.get("games", []))

        elif message["type"] == "JOIN_OK":
            response.update(
                status="OK",
                message=message,
            )

        elif message["type"] == "JOIN_ERR":
            response.update(
                status="ERR",
                reason=message.get("reason"),
            )

        elif message["type"] == "GUESS_RESULT":
            response.update(message)

        else:
            return False

        event.set()
        return True

# funcao que lista os peers conhecidos na rede filtrando por namespace
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

# funcao que lista apenas os peers com conexao ativa no momento
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


# funcao que listas os rtt de cada peer
    def listar_rtt(self):
        return [
            {"peer_id": peer["peer_id"], "rtt": peer.get("rtt")}
            for peer in self.tabela.listar()
            if peer.get("rtt") is not None
        ]

# funcao que consulta o rendezvous e sincroniza as conexoes com os peers
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


# funcao que altera o nivel de exibicao dos logs da aplicacao
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

# funcao que encerra de forma limpa uma partida ativa como host ou jogador
    def encerramento_limpo(self):
        if self.host is not None:
            return self.cancelar()
        if self.player is not None:
            return self.sair()
        return True

# funcao que permite o envio de mensagem para todos os jogadores da sala 
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

# funcao que cria uma nova partida
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

        
# funcao que possibilita o cancelamento da partida 
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

# funcao que permite e trata as condicoes de iniciio da partida 
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

# # funcao que monitora em loop o tempo limite de cada turno
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

# funcao que lista as partidas disponiveis 
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
        tokens_peers = {}
        for peer_id in peers:
            event = threading.Event()
            token = criar_envelope("GAME_LIST")["msg_id"]
            self.pending[token] = (event, peer_id, [])
            tokens_peers[peer_id] = token
            message = criar_envelope("GAME_LIST", src=self.peer_id, dst=peer_id, msg_id=token)
            try:
                self.enviar(peer_id, message)
            except Exception:
                continue
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.05)
        for peer_id, token in tokens_peers.items():
            pendente = self.pending.pop(token, None)
            if pendente is not None:
                event, owner, games = pendente
                resposta[peer_id] = games
        self.games_by_host = {
            game["host"]: game
            for games in resposta.values()
            for game in games
        }
        return resposta

# funcao para a entrada na partida 
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

# funcao de sair da partida 
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

# funcao de chutar uma letra 
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

# funcao que permite a visualização dos status da partida 
    def status(self):
        if self.host is not None:
            host = self.host
            jogadores = ", ".join(host.jogadores) or "-"
            erradas = ", ".join(host.jogo.letras_erradas) or "-"
            if host.estado == "RUNNING" and host.turn_started_at is not None:
                decorrido = time.monotonic() - host.turn_started_at
                restante = max(0, math.ceil(host.turn_timeout - decorrido))
                vez = host.jogador_da_vez()
            else:
                restante = "-"
                vez = "-"
            return (
                f"[Game] {host.game_id} (host: {self.peer_id}) status: {host.estado}\n"
                f"[Game] Palavra: {' '.join(host.jogo.mascara())} "
                f"Vidas: {host.jogo.vidas}/{self.config.get('lives', 6)} "
                f"Erradas: {erradas}\n"
                f"[Game] Jogadores: {jogadores} Vez de: {vez} "
                f"Tempo restante: {restante}{' s' if restante != '-' else ''}"
            )
        if self.player is not None:
            jogadores = ", ".join(self.player.players) or "-"
            erradas = ", ".join(self.player.wrong_letters) or "-"
            vez = self.player.turn or "-"
            se_eu = " (você)" if self.player.turn == self.peer_id else ""
            if self.player.status == "PLAYING" and self.player.turn_started_at is not None:
                decorrido = time.monotonic() - self.player.turn_started_at
                restante = max(
                    0,
                    math.ceil(self.player.turn_timeout - decorrido),
                )
            else:
                restante = "-"
            return (
                f"[Game] {self.player.game_id} (host: {self.player.host_id}) status: {self.player.status}\n"
                f"[Game] Palavra: {' '.join(self.player.masked)} "
                f"Vidas: {self.player.lives} Erradas: {erradas}\n"
                f"[Game] Jogadores: {jogadores} Vez de: {vez}{se_eu} "
                f"Tempo restante: {restante}{' s' if restante != '-' else ''}"
            )
        return "[Game] no active game"

#funcao que realiza o gameover e caso de vitoria 
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

# funcao principal que recebe e roteia todas as mensagens vindas da rede p2p
    def handler(self, message, peer_id, config, tabela):
        type_name = message.get("type")

        if type_name == "PEER_DOWN":
            if self.host is not None and peer_id in self.host.jogadores:
                self.host.remover_jogador(peer_id, desconexao= True)
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
            self.resolver_pendente(message,peer_id)
            return

        if type_name == "JOIN":
            reason = None

            if self.host is None:
                reason = "unknown_game"
            elif message.get("game_id") != self.host.game_id:
                reason = "unknown_game"
            elif self.host.estado == "FINISHED":
                reason = "game_finished"
            elif self.host.estado == "RUNNING":
                if peer_id in self.host.desconectados:
                    self.host.desconectados.remove(peer_id)
                    self.host.jogadores.append(peer_id)
                    response = criar_envelope(
                        "JOIN_OK",
                        src=self.peer_id,
                        dst=peer_id,
                        msg_id=message.get("msg_id"),
                        game_id=self.host.game_id,
                        players=self.host.jogadores.copy(),
                        rejoin=True,
                    )
                    self.enviar(peer_id, response)

                    self.host.seq += 1
                    for player_id in self.host.jogadores:
                        self.enviar(player_id, self.host.state(player_id))
                    return

                if peer_id in self.host.jogadores:
                    reason = "already_joined"
                else:
                    reason = "game_running"
            elif self.host.estado == "OPEN":
                if peer_id in self.host.jogadores:
                    reason = "already_joined"
                elif len(self.host.jogadores) >= self.host.max_jogadores:
                    reason = "game_full"
                elif not self.host.adicionar_jogador(peer_id):
                    reason = "game_full"
                else:
                    response = criar_envelope(
                        "JOIN_OK", src=self.peer_id, dst=peer_id,
                        msg_id=message.get("msg_id"), game_id=self.host.game_id,
                        players=self.host.jogadores.copy(), rejoin=False,
                    )
                    self.enviar(peer_id, response)

                    self.host.seq += 1
                    for player_id in self.host.jogadores:
                        self.enviar(player_id, self.host.state(player_id))
                    return

            if reason is not None:
                response = criar_envelope(
                    "JOIN_ERR", src=self.peer_id, dst=peer_id,
                    msg_id=message.get("msg_id"), game_id=message.get("game_id"),
                    reason=reason,
                )
                self.enviar(peer_id, response)
            return

        if type_name == "JOIN_OK":
            if not self.resolver_pendente(message, peer_id):
                return
            if self.player is None:
                self.player = GamePlayer(
                    self.peer_id,
                    message["game_id"],
                    peer_id,
                    word_hash="",
                    word_length=0,
                    lives=int(self.config.get("lives", 6)),
                    players=message["players"],
                    turn_timeout=int(self.config.get("turn_timeout", 30)),
                )
            return

        if type_name == "JOIN_ERR":
            self.resolver_pendente(message,peer_id)
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
            with self.lock:
                if self.player is None or self.player.game_id != message.get("game_id"):
                    self.player = GamePlayer(
                        self.peer_id,
                        message["game_id"],
                        peer_id,
                        message["word_hash"],
                        message["word_length"],
                        message["lives"],
                        message["players"],
                        turn_timeout=int(message["turn_timeout"]),
                    )
                else:
                    self.player.word_hash = message["word_hash"]
                    self.player.word_length = message["word_length"]
                    self.player.masked = "_" * int(message["word_length"])
                    self.player.lives = message["lives"]
                    self.player.players = list(message.get("players", []))
                    self.player.turn_timeout = int(message["turn_timeout"])
                self.player.status = "PLAYING"
                self.player.last_seq = 0
                self.player.turn = None
                self.player.wrong_letters = []
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
            if not self.resolver_pendente(message, peer_id):
                return
            if self.player is not None:
                self.player.processar_guess_result(message)
            return

        if type_name == "GAME_OVER":
            if self.player is not None:
                resultado = self.player.processar_game_over(message)
                word = resultado.get("word")
                winner = resultado.get("winner")
                result = resultado.get("result")
                scores = resultado.get("scores", {})
                if winner:
                    print(
                        f"[Game] GAME_OVER {result} word={word} "
                        f"winner={winner} scores={scores}"
                    )
                else:
                    print(
                        f"[Game] GAME_OVER {result} word={word} "
                        f"scores={scores}"
                    )
                if not resultado.get("hash_valid", True):
                    logger.warning("[Player] host cheated: hash mismatch")
            else:
                logger.info(
                    "[Player] GAME_OVER %s",
                    message.get("result"),
                )
            self.player = None
