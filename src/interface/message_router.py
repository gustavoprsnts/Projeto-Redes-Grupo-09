from src.game.game_host import GameHost
from src.game.game_player import GamePlayer


class MessageRouter:
    def __init__(
        self,
        host: GameHost | None = None,
        player: GamePlayer | None = None,
    ):
        self.host = host
        self.player = player

    def route(self, message: dict) -> list[dict]:
        message_type = message.get("type")

        if message_type == "GUESS":
            return self._route_guess(message)

        if self.player is None:
            raise RuntimeError("Nenhum GamePlayer foi configurado")

        if message_type == "STATE":
            self.player.processar_state(message)
            return []
        if message_type == "GUESS_RESULT":
            self.player.processar_guess_result(message)
            return []
        if message_type == "GAME_OVER":
            self.player.processar_game_over(message)
            return []

        raise ValueError(f"Tipo de mensagem não suportado: {message_type}")

    def _route_guess(self, message: dict) -> list[dict]:
        if self.host is None:
            raise RuntimeError("Nenhum GameHost foi configurado")

        result = self.host.processar_guess(
            jogador=message["src"],
            letra=message.get("letter"),
            palavra=message.get("word"),
            msg_id=message.get("msg_id"),
        )

        responses = [
            {
                key: value
                for key, value in result.items()
                if key not in {"state", "game_over"}
            }
        ]
        if "state" in result:
            responses.append(result["state"])
        if "game_over" in result:
            responses.append(result["game_over"])
        return responses
