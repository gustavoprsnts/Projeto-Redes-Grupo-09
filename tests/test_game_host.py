from src.game.game_host import GameHost
from src.game.game_player import GamePlayer

game_host = GameHost(
    host_id="alice@CIC", 
    palavra="banana",
    vidas=2,
    max_jogadores=3,)

assert game_host.host_id == "alice@CIC"
assert game_host.jogo.palavra == "banana"
assert game_host.jogo.vidas == 2
assert game_host.max_jogadores == 3
assert game_host.turn_timeout == 30
assert game_host.estado == "OPEN"
assert game_host.jogadores == []

assert game_host.adicionar_jogador("bob@CIC") is True
assert game_host.adicionar_jogador("carol@CIC") is True

assert game_host.jogadores == [
    "bob@CIC",
    "carol@CIC",
]

assert game_host.adicionar_jogador("bob@CIC") is False
assert game_host.iniciar() is True
assert game_host.estado == "RUNNING"
assert game_host.jogador_da_vez() == "bob@CIC"

game_host.avancar_turno()
assert game_host.jogador_da_vez() == "carol@CIC"

game_host.avancar_turno()
assert game_host.jogador_da_vez() == "bob@CIC"

resultado = game_host.processar_guess("carolina@CIC")
assert resultado["accepted"] is False
assert resultado["reason"] == "unknown_player"
assert resultado["type"] == "GUESS_RESULT"

resultado = game_host.processar_guess("carol@CIC")
assert resultado["accepted"] is False
assert resultado["reason"] == "not_your_turn"
assert resultado["type"] == "GUESS_RESULT"

resultado = game_host.processar_guess("bob@CIC")
assert resultado["accepted"] is False
assert resultado["reason"] == "invalid_guess"
assert resultado["type"] == "GUESS_RESULT"

resultado = game_host.processar_guess("bob@CIC", ".")
assert resultado["accepted"] is False
assert resultado["reason"] == "invalid_letter"
assert resultado["type"] == "GUESS_RESULT"

resultado = game_host.processar_guess("bob@CIC", "b")

assert resultado["accepted"] is True
assert resultado["correct"] is True
assert resultado["status"] == "RUNNING"
assert resultado["type"] == "GUESS_RESULT"
assert resultado["src"] == "alice@CIC"
assert resultado["dst"] == "bob@CIC"
assert resultado["ttl"] == 1

assert resultado["state"]["seq"] == 2
assert resultado["state"]["type"] == "STATE"
assert resultado["state"]["src"] == "alice@CIC"
assert resultado["state"]["dst"] == "bob@CIC"
assert resultado["state"]["ttl"] == 1
assert resultado["state"]["masked"] == "b_____"
assert resultado["state"]["turn"] == "carol@CIC"

resultado = game_host.processar_guess("carol@CIC", "b")
assert resultado["accepted"] is False
assert resultado["reason"] == "letter_already_used"
assert resultado["type"] == "GUESS_RESULT"


resultado = game_host.processar_guess("carol@CIC", "x")

assert resultado["accepted"] is True
assert resultado["correct"] is False
assert game_host.jogo.vidas == 1

resultado = game_host.processar_guess(
    "bob@CIC",
    palavra="banana"
)

assert resultado["accepted"] is True
assert resultado["correct"] is True
assert "game_over" in resultado
assert game_host.estado == "FINISHED"

timeout_host = GameHost(
    host_id="alice@CIC",
    palavra="banana",
    turn_timeout=0,
)

timeout_host.adicionar_jogador("bob@CIC")
timeout_host.iniciar()

estado = timeout_host.processar_timeout()

assert estado is not None
assert estado["last_guess"]["timeout"] is True
assert estado["seq"] == 2

def enviar_para_host(mensagem: dict) -> dict:
    return host.processar_guess(
        jogador=mensagem["src"],
        letra=mensagem.get("letter"),
        palavra=mensagem.get("word"),
        msg_id=mensagem.get("msg_id"),
    )

host = GameHost(
        host_id="alice@CIC",
        palavra="banana",
)

host.adicionar_jogador("bob@CIC")
host.adicionar_jogador("ana@CIC")
host.iniciar()

game_start = host.game_start("bob@CIC")
assert game_start["type"] == "GAME_START"
assert game_start["src"] == "alice@CIC"
assert game_start["dst"] == "bob@CIC"
assert game_start["ttl"] == 1
assert game_start["players"] == ["bob@CIC", "ana@CIC"]

player = GamePlayer(
        player_id=("bob@CIC"),
        game_id=host.game_id,
        host_id="alice@CIC",
        word_hash=host.jogo.word_hash(),
        word_length=6,
        lives=6,
        players=["bob@CIC", "ana@CIC"],
        enviar=enviar_para_host,
)

player2 = GamePlayer(
        player_id=("ana@CIC"),
        game_id=host.game_id,
        host_id="alice@CIC",
        word_hash=host.jogo.word_hash(),
        word_length=6,
        lives=6,
        players=["bob@CIC", "ana@CIC"],
        enviar=enviar_para_host,
)

def aplicar_state(resultado: dict) -> None:
    if "state" in resultado:
        player.processar_state(resultado["state"])
        player2.processar_state(resultado["state"])


resultado = player.enviar_palpite_letra("b")

assert resultado["accepted"] is True
aplicar_state(resultado)

assert player.masked == "b_____"
assert player.last_seq == 2
assert player.turn == "ana@CIC"

resultado = player2.enviar_palpite_letra("a")

assert resultado["accepted"] is True
aplicar_state(resultado)

assert player.masked == "ba_a_a"
assert player.last_seq == 3
assert player.turn == "bob@CIC"

resultado = player.enviar_palpite_letra("x")
assert resultado["accepted"] is True
aplicar_state(resultado)

assert player.turn == "ana@CIC"

resultado = player2.enviar_palpite_palavra("btnana")
assert resultado["accepted"] is True
aplicar_state(resultado)
assert player.turn == "bob@CIC"

resultado = player.enviar_palpite_palavra("tanana")
assert resultado["accepted"] is True
aplicar_state(resultado)
assert player.turn == "ana@CIC"

resultado = player2.enviar_palpite_palavra("btnqna")
assert resultado["accepted"] is True
aplicar_state(resultado)
assert player.turn == "bob@CIC"

resultado = player.enviar_palpite_palavra("btnqna")
assert resultado["accepted"] is True
aplicar_state(resultado)
assert player.turn == "ana@CIC"

resultado = player2.enviar_palpite_palavra("btnapa")
assert resultado["accepted"] is True
assert "game_over" in resultado
assert host.estado == "FINISHED"