from src.game.hangman import Hangman

jogo = Hangman("banana", vidas=2)

assert jogo.mascara() == "______"

assert jogo.palpite("a") == {
    "accepted": True,
    "correct": True,
    "status": "RUNNING",
}
assert jogo.mascara() == "_a_a_a"

assert jogo.tentar_palavra("macaco") == {
    "accepted": True,
    "correct": False,
    "status": "RUNNING",
}
assert jogo.vidas == 1

assert jogo.palpite("a") == {
    "accepted": False,
    "reason": "letter_already_used",
}

assert jogo.tentar_palavra("batata") == {
    "accepted": True,
    "correct": False,
    "status": "LOST",
}
assert jogo.estado == "LOST"

assert jogo.palpite("n") == {
    "accepted": False,
    "reason": "game_not_running",
}

assert jogo.snapshot() == {
    "masked": "_a_a_a",
    "wrong_letters": [],
    "lives": 0,
    "status": "LOST",
}




