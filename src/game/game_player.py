from collections.abc import Callable
import hashlib
from time import monotonic


from conections.protocolo import criar_envelope

class GamePlayer:
    def __init__(
        self,
        player_id: str,
        game_id: str,
        host_id: str,
        word_hash: str,
        word_length: int,
        lives: int,
        players: list[str],
        enviar: Callable[[dict], dict] | None = None,
        turn_timeout: int = 30,

    ):
        self.player_id = player_id
        self.game_id = game_id
        self.host_id = host_id
        self.word_hash = word_hash
        self.word_length = word_length
        self.lives = lives
        self.players = players
        self.masked = "_" * word_length
        self.wrong_letters: list[str] = []
        self.turn = None
        self.last_seq = 0
        self.status = "JOINED"
        self.enviar = enviar
    #funcao que envia o palpite de uma letra para o host e retorna um dicionário com o resultado do palpite
    def enviar_palpite_letra(self, letra: str) -> dict:
        mensagem = criar_envelope(
            tipo="GUESS",
            src=self.player_id,
            dst=self.host_id,
            letter=letra,
            game_id=self.game_id,
        )

        if self.enviar is None:
            raise RuntimeError("Nenhuma função de envio foi configurada")

        return self.enviar(mensagem)
    #funcao que envia o palpite de uma palavra inteira para o host e retorna um dicionário com o resultado do palpite
    def enviar_palpite_palavra(self, palavra: str) -> dict:
        mensagem = criar_envelope(
            tipo="GUESS",
            src=self.player_id,
            dst=self.host_id,
            game_id=self.game_id,
            word=palavra,
        )

        if self.enviar is None:
            raise RuntimeError("Nenhuma função de envio foi configurada")

        return self.enviar(mensagem)
    #funcao que atualiza o estado local do jogador com base no pacote de estado enviado pelo Host.
    def processar_state(self, mensagem: dict) -> bool:
        if mensagem["seq"] <= self.last_seq:
            return False

        turno_anterior = self.turn
        self.last_seq = mensagem["seq"]
        self.masked = mensagem["masked"]
        self.wrong_letters = mensagem["wrong_letters"].copy()
        self.lives = mensagem["lives"]
        self.turn = mensagem["turn"]
        self.players = mensagem["players"].copy()
        self.status = mensagem.get("status", "PLAYING")
        if turno_anterior != self.turn:
            self.turn_started_at = monotonic()

        return True
    #processa o retorno do palpite enviado para o host, atualizando o estado local do jogador e retornando um dicionário com o resultado do palpite
    def processar_guess_result(self, mensagem: dict) -> dict:
        if not mensagem["accepted"]:
            return {
                "accepted": False,
                "reason": mensagem["reason"],
            }

        return {
            "accepted": True,
            "correct": mensagem["correct"],
        }
    #funcao que processa a mensagem de GAME_OVER enviada pelo host
    def processar_game_over(self, mensagem: dict) -> dict:
        if mensagem.get("type") != "GAME_OVER":
            return {
                "accepted": False,
                "reason": "invalid_message",
            }

        palavra = mensagem.get("word")
        if not isinstance(palavra, str):
            return {
                "accepted": False,
                "reason": "missing_word",
            }
        #verifica se o hash da palavra recebida é igual ao hash da palavra que o host enviou no início do jogo
        hash_valido = self.verificar_hash(palavra)
        self.status = "FINISHED"

        resultado = {
            "accepted": True,
            "status": "FINISHED",
            "result": mensagem.get("result"),
            "word": palavra,
            "winner": mensagem.get("winner"),
            "scores": mensagem.get("scores", {}),
            "hash_valid": hash_valido,
        }
        if not hash_valido:
            resultado["warning"] = "host cheated: hash mismatch"

        return resultado
        
    #gera o hash da palavra
    def calcular_hash(self, palavra: str) -> str:
        return hashlib.sha256(
            palavra.encode("utf-8")
        ).hexdigest()
    #verufica se o hash da palavra recebida é igual ao hash da palavra que o host enviou no início do jogo
    def verificar_hash(self, palavra: str) -> bool:
        hash_recebido = self.calcular_hash(palavra)
        return hash_recebido == self.word_hash