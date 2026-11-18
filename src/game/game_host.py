from collections.abc import Callable
from time import monotonic
from uuid import uuid4

from game.hangman import Hangman
from conections.protocolo import criar_envelope

IDLE = "IDLE"
OPEN = "OPEN"
RUNNING = "RUNNING"
FINISHED = "FINISHED"

# classe para host de partida 
class GameHost:
    # funcao que inicializa o host da partida com as configuracoes e regras do jogo
    def __init__(
        self,
        host_id: str,
        palavra: str,
        vidas: int = 6,
        max_jogadores: int = 4,
        turn_timeout: int = 30,
        enviar: Callable[[str, dict], None] | None = None,
    ):
        self.host_id = host_id
        self.game_id = f"{host_id}/{uuid4().hex[:8]}"
        self.jogo = Hangman(palavra, vidas)
        self.max_jogadores = max_jogadores
        self.turn_timeout = turn_timeout
        self.enviar_mensagem = enviar

        self.estado = OPEN
        self.jogadores: list[str] = []
        self.historico_jogadores: set[str] = set()
        self.desconectados: set[str] = set()
        self.turno_atual = 0
        self.seq = 0
        self.scores: dict[str, int] = {}
        self.last_guess: dict | None = None
        self.turn_started_at: float | None = None


# funcao que adiciona um novo jogador a sala caso esteja aberta e com vagas
    def adicionar_jogador(self, jogador: str) -> bool:
        if self.estado != OPEN:
            return False
        if len(self.jogadores) >= self.max_jogadores:
            return False
        if jogador in self.jogadores:
            return False

        self.jogadores.append(jogador)
        self.historico_jogadores.add(jogador)
        self.desconectados.discard(jogador)
        self.scores[jogador] = 0
        return True


    
# funcao que remove um jogador da partida, lidando com reconexoes ou fim de jogo
    def remover_jogador(self,jogador: str, desconexao: bool = False) -> bool:
        if jogador not in self.jogadores:
            return False

        index = self.jogadores.index(jogador)
        era_a_vez = (
            self.estado == RUNNING
            and self.turno_atual == index
        )

        del self.jogadores[index]

        if desconexao and self.estado == RUNNING:
            self.desconectados.add(jogador)
        else:
            self.desconectados.discard(jogador)
            self.participantes_originais.discard(jogador)

            if self.estado != RUNNING:
                self.scores.pop(jogador, None)

        if not self.jogadores:
            if self.estado == RUNNING:
                self.finalizar()
            return True

        if self.estado == RUNNING:
            if index < self.turno_atual:
                self.turno_atual -= 1
            elif era_a_vez:
                self.turno_atual %= len(self.jogadores)

            self.turn_started_at = monotonic()
            self.seq += 1

        return True


# funcao que verica qual o jogador do turno 
    def jogador_da_vez(self) -> str:
        if not self.jogadores:
            raise ValueError("A partida não possui jogadores")
        return self.jogadores[self.turno_atual]

# funcao que avanca o turno para o proximo jogador na sequencia
    def avancar_turno(self) -> None:
        if self.jogadores:
            self.turno_atual = (self.turno_atual + 1) % len(self.jogadores)
            self.turn_started_at = monotonic()


# funcao que inicia oficialmente a partida se houver jogadores cadastrados
    def iniciar(self) -> bool:
        if self.estado != OPEN or not self.jogadores:
            return False

        self.estado = RUNNING
        self.seq = 1
        self.turno_atual = 0
        self.last_guess = None
        self.turn_started_at = monotonic()
        return True
# funcao que trata o encerramento da seçao 
    def finalizar(self) -> None:
        self.estado = FINISHED

# funcao para setar o estado como Running ou seja ocorrendo partida 
    def esta_em_andamento(self) -> bool:
        return self.estado == RUNNING

# funcao que processa tentativa 
    def processar_guess(
        self,
        jogador: str,
        letra: str | None = None,
        palavra: str | None = None,
        msg_id: str | None = None,
    ) -> dict:
        if self.estado != RUNNING:
            return self.guess_result(
                jogador, {"accepted": False, "reason": "game_not_running"}, msg_id
            )
        if jogador not in self.jogadores:
            return self.guess_result(
                jogador, {"accepted": False, "reason": "unknown_player"}, msg_id
            )
        if jogador != self.jogador_da_vez():
            return self.guess_result(
                jogador, {"accepted": False, "reason": "not_your_turn"}, msg_id
            )
        if (letra is None) == (palavra is None):
            return self.guess_result(
                jogador, {"accepted": False, "reason": "invalid_guess"}, msg_id
            )

        masked_before = self.jogo.mascara()
        if letra is not None:
            resultado = self.jogo.palpite(letra)
            guess_data = {"player": jogador, "letter": letra}
        else:
            resultado = self.jogo.tentar_palavra(palavra or "")
            guess_data = {"player": jogador, "word": palavra}

        resposta = self.guess_result(jogador, resultado, msg_id)
        if not resultado["accepted"]:
            return resposta

        resultado = resposta

        guess_data["correct"] = resultado["correct"]
        self.last_guess = guess_data
        if letra is not None and resultado["correct"]:
            revealed = sum(
                1
                for antes, depois in zip(masked_before, self.jogo.mascara())
                if antes == "_" and depois != "_"
            )
            self.scores[jogador] += revealed
        elif palavra is not None and resultado["correct"]:
            self.scores[jogador] += masked_before.count("_")

        jogador_da_jogada = jogador

        if self.jogo.estado in ("WON", "LOST"):
            self.finalizar()
            resultado["game_over"] = self.game_over(
                jogador_da_jogada,
                jogador_da_jogada,
            )
        else:
            self.avancar_turno()
            self.seq += 1
            resultado["state"] = self.state(dst=jogador)

        return resultado

# funcao que cria o envelope de resposta para o resultado de um palpite
    def guess_result(self, jogador: str, resultado: dict, msg_id: str | None) -> dict:
        resposta = criar_envelope(
            tipo="GUESS_RESULT",
            src=self.host_id,
            dst=jogador,
            msg_id=msg_id,
            game_id=self.game_id,
        )
        resposta.update(resultado)
        return resposta
# funcao que gera o envelope com o estado atual
    def state(self, dst: str | None = None) -> dict:
        return criar_envelope(
            tipo="STATE",
            src=self.host_id,
            dst=dst,
            game_id=self.game_id,
            seq=self.seq,
            **self.jogo.snapshot(),
            turn=self.jogador_da_vez(),
            players=self.jogadores.copy(),
            last_guess=self.last_guess.copy() if self.last_guess else None,
        )

#  # funcao que gera o envelope com o estado atual
    def game_start(self, dst: str | None = None) -> dict:
        return criar_envelope(
            tipo="GAME_START",
            src=self.host_id,
            dst=dst,
            game_id=self.game_id,
            players=self.jogadores.copy(),
            lives=self.jogo.vidas,
            word_length=len(self.jogo.palavra),
            word_hash=self.jogo.word_hash(),
            turn_timeout=self.turn_timeout,
        )

# funcao que verifica se o tempo limite do turno atual expirou
    def processar_timeout(self) -> dict | None:
        if self.estado != RUNNING or self.turn_started_at is None:
            return None

        if monotonic() - self.turn_started_at < self.turn_timeout:
            return None

        self.last_guess = {
            "player": self.jogador_da_vez(),
            "timeout": True,
        }
        self.avancar_turno()
        self.seq += 1
        return self.state(dst=self.jogador_da_vez())

# funcao que processa fim da partida e cria envelope  
    def game_over(self, vencedor: str | None = None, dst: str | None = None) -> dict:
        result = "WON" if self.jogo.estado == "WON" else "LOST"
        winner = vencedor if result == "WON" else None

        return criar_envelope(
            tipo="GAME_OVER",
            src=self.host_id,
            dst=dst,
            game_id=self.game_id,
            result=result,
            word=self.jogo.palavra,
            winner=winner,
            scores=self.scores.copy(),
        )
