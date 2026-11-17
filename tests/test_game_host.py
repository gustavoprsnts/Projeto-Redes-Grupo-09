from src.game.game_host import GameHost
from src.game.game_player import GamePlayer

# game_host = GameHost(
#     host_id="alice@CIC", 
#     palavra="banana",
#     vidas=2,
#     max_jogadores=3,)

# assert game_host.host_id == "alice@CIC"
# assert game_host.jogo.palavra == "banana"
# assert game_host.jogo.vidas == 2
# assert game_host.max_jogadores == 3
# assert game_host.turn_timeout == 30
# assert game_host.estado == "OPEN"
# assert game_host.jogadores == []

# assert game_host.adicionar_jogador("bob@CIC") is True
# assert game_host.adicionar_jogador("carol@CIC") is True

# assert game_host.jogadores == [
#     "bob@CIC",
#     "carol@CIC",
# ]

# assert game_host.adicionar_jogador("bob@CIC") is False
# assert game_host.iniciar() is True
# assert game_host.estado == "RUNNING"
# assert game_host.jogador_da_vez() == "bob@CIC"

# game_host.avancar_turno()
# assert game_host.jogador_da_vez() == "carol@CIC"

# game_host.avancar_turno()
# assert game_host.jogador_da_vez() == "bob@CIC"

# assert game_host.processar_guess("carolina@CIC") == {
#     "accepted": False,
#     "reason": "unknown_player"
# }

# assert game_host.processar_guess("carol@CIC") == {
#     "accepted": False,
#     "reason": "not_your_turn"
# }

# assert game_host.processar_guess("bob@CIC") == {
#     "accepted": False,
#     "reason": "invalid_guess"
# }

# assert game_host.processar_guess("bob@CIC", ".") == {
#     "accepted": False, 
#     "reason": "invalid_letter"
# }

# resultado = game_host.processar_guess("bob@CIC", "b")

# assert resultado["accepted"] is True
# assert resultado["correct"] is True
# assert resultado["status"] == "RUNNING"

# assert resultado["state"]["seq"] == 2
# assert resultado["state"]["masked"] == "b_____"
# assert resultado["state"]["turn"] == "carol@CIC"

# assert game_host.processar_guess("carol@CIC", "b") == {
#     "accepted": False,
#     "reason": "letter_already_used"
# }


# resultado = game_host.processar_guess("carol@CIC", "x")

# assert resultado["accepted"] is True
# assert resultado["correct"] is False
# assert game_host.jogo.vidas == 1

# resultado = game_host.processar_guess(
#     "bob@CIC",
#     palavra="banana"
# )

# assert resultado["accepted"] is True
# assert resultado["correct"] is True
# assert "game_over" in resultado
# assert game_host.estado == "FINISHED"

# timeout_host = GameHost(
#     host_id="alice@CIC",
#     palavra="banana",
#     turn_timeout=0,
# )

# timeout_host.adicionar_jogador("bob@CIC")
# timeout_host.iniciar()

# estado = timeout_host.processar_timeout()

# assert estado is not None
# assert estado["last_guess"]["timeout"] is True
# assert estado["seq"] == 2

def enviar_para_host(mensagem: dict) -> dict:
        return host.processar_guess(
            jogador = mensagem["src"],
            letra = mensagem.get("letter"),
            palavra = mensagem.get("word"),
        )

host = GameHost(
        host_id="alice@CIC",
        palavra="banana",
)

host.adicionar_jogador("bob@CIC")
host.iniciar()

player = GamePlayer(
        player_id=("bob@CIC"),
        game_id=host.game_id,
        word_hash=host.jogo.word_hash(),
        word_length=6,
        lives=6,
        players=["bob@CIC"],
        enviar=enviar_para_host,
)

resultado = player.enviar_palpite_letra("b")
print(resultado)
print("\n")
resultado = player.enviar_palpite_letra("x")
print(resultado)
print("\n")

resultado = player.enviar_palpite_palavra("btnana")
print(resultado)
print("\n")
resultado = player.enviar_palpite_palavra("banana")
print(resultado)