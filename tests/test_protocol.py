from src.protocol import criar_envelope


mensagem = criar_envelope(
    tipo="GUESS",
    src="bob@CIC",
    dst="alice@CIC",
    game_id="alice@CIC/abc12345",
    letter="a",
)

assert mensagem["type"] == "GUESS"
assert mensagem["src"] == "bob@CIC"
assert mensagem["dst"] == "alice@CIC"
assert mensagem["ttl"] == 1
assert mensagem["game_id"] == "alice@CIC/abc12345"
assert mensagem["letter"] == "a"
assert isinstance(mensagem["msg_id"], str)
assert mensagem["msg_id"]

outra_mensagem = criar_envelope("PING")

assert outra_mensagem["type"] == "PING"
assert outra_mensagem["ttl"] == 1
assert "src" not in outra_mensagem
assert "dst" not in outra_mensagem
assert mensagem["msg_id"] != outra_mensagem["msg_id"]
