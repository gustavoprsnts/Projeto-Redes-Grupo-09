from src.game.game_player import GamePlayer
from src.game.hangman import Hangman


def criar_jogador(word_hash: str) -> GamePlayer:
    return GamePlayer(
        player_id="bob@CIC",
        game_id="alice@CIC/abc12345",
        host_id="alice@CIC",
        word_hash=word_hash,
        word_length=6,
        lives=6,
        players=["bob@CIC"],
    )


palavra = "banana"
hash_correto = Hangman(palavra).word_hash()

for resultado in ("WON", "LOST", "ABORTED"):
    jogador = criar_jogador(hash_correto)
    mensagem = {
        "type": "GAME_OVER",
        "result": resultado,
        "word": palavra,
    }

    resposta = jogador.processar_game_over(mensagem)

    assert resposta["accepted"] is True
    assert resposta["hash_valid"] is True
    assert resposta["result"] == resultado
    assert jogador.status == "FINISHED"


jogador = criar_jogador(hash_correto)
resposta = jogador.processar_game_over(
    {
        "type": "GAME_OVER",
        "result": "WON",
        "word": "macaco",
    }
)

assert resposta["accepted"] is True
assert resposta["hash_valid"] is False
assert resposta["warning"] == "host cheated: hash mismatch"
assert jogador.status == "FINISHED"


jogador = criar_jogador(hash_correto)
state = {
    "seq": 1,
    "masked": "_a_a_a",
    "wrong_letters": ["e"],
    "lives": 5,
    "turn": "bob@CIC",
    "players": ["bob@CIC"],
    "status": "RUNNING",
}

assert jogador.processar_state(state) is True
assert jogador.last_seq == 1
assert jogador.masked == "_a_a_a"
assert jogador.wrong_letters == ["e"]
assert jogador.lives == 5
assert jogador.turn == "bob@CIC"
assert jogador.players == ["bob@CIC"]
assert jogador.status == "RUNNING"

state_older = {
    **state,
    "seq": 1,
    "masked": "______",
}

assert jogador.processar_state(state_older) is False
assert jogador.masked == "_a_a_a"

state_newer = {
    **state,
    "seq": 2,
    "masked": "banana",
    "turn": None,
}

assert jogador.processar_state(state_newer) is True
assert jogador.last_seq == 2
assert jogador.masked == "banana"

assert jogador.processar_guess_result(
    {
        "accepted": True,
        "correct": True,
    }
) == {
    "accepted": True,
    "correct": True,
}

assert jogador.processar_guess_result(
    {
        "accepted": False,
        "reason": "not_your_turn",
    }
) == {
    "accepted": False,
    "reason": "not_your_turn",
}
