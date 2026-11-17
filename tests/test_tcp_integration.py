from threading import Event

from src.conections.tcp_transport import TcpPeerClient, TcpPeerServer
from src.game.game_host import GameHost
from src.game.game_player import GamePlayer
from src.message_router import MessageRouter


host = GameHost("alice@CIC", "banana", vidas=2)
host.adicionar_jogador("bob@CIC")
assert host.iniciar() is True

host_router = MessageRouter(host=host)
server = TcpPeerServer("127.0.0.1", 0, host_router.route)
server.start()

received_state = Event()
received_result: list[dict] = []


def on_player_message(message: dict) -> None:
    received_result.append(message)
    if message.get("type") == "STATE":
        received_state.set()


client = TcpPeerClient(on_player_message)
client.connect(*server.address)


def send_to_host(message: dict) -> dict:
    client.send(message)
    return {"sent": True}


player = GamePlayer(
    player_id="bob@CIC",
    game_id=host.game_id,
    host_id="alice@CIC",
    word_hash=host.jogo.word_hash(),
    word_length=6,
    lives=2,
    players=["bob@CIC"],
    enviar=send_to_host,
)

player.enviar_palpite_letra("b")
assert received_state.wait(2)

client.close()
server.stop()

assert any(message["type"] == "GUESS_RESULT" for message in received_result)
state_messages = [
    message for message in received_result if message["type"] == "STATE"
]
assert state_messages[0]["masked"] == "b_____"
assert state_messages[0]["dst"] == "bob@CIC"
