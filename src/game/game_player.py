from collections.abc import Callable

class GamePlayer:
    def __init__(
        self,
        player_id: str,
        game_id: str,
        word_hash: str,
        word_length: int,
        lives: int,
        players: list[str],
        enviar: Callable[[dict], dict] | None = None,

    ):
        self.player_id = player_id
        self.game_id = game_id
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

    def enviar_palpite_letra(self, letra: str) -> dict:
        mensagem = {
            "type": "GUESS",
            "src": self.player_id,
            "game_id": self.game_id,
            "letter": letra,
            "ttl": 1,
        }

        if self.enviar is None:
            raise RuntimeError("Nenhuma função de envio foi configurada")

        return self.enviar(mensagem)

    def enviar_palpite_palavra(self, palavra: str) -> dict:
        mensagem = {
            "type": "GUESS",
            "src": self.player_id,
            "game_id": self.game_id,
            "word": palavra,
            "ttl": 1,
        }

        if self.enviar is None:
            raise RuntimeError("Nenhuma função de envio foi configurada")

        return self.enviar(mensagem)

    
