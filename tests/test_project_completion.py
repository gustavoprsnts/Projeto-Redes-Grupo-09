import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from conections.peer_table import Estado, PeerTable
from forcaAPP import P2PForcaApp
from game.game_host import GameHost


class FakeTable(PeerTable):
    def __init__(self):
        super().__init__("alice@CIC", 3, 2, 60)


class HostCompletionTests(unittest.TestCase):
    def test_remove_player_before_turn_adjusts_next_player(self):
        host = GameHost("alice@CIC", "banana", vidas=2)
        host.adicionar_jogador("bob@CIC")
        host.adicionar_jogador("ana@CIC")
        host.adicionar_jogador("carol@CIC")
        host.iniciar()

        assert host.remover_jogador("bob@CIC")
        self.assertEqual(host.jogadores, ["ana@CIC", "carol@CIC"])
        self.assertEqual(host.jogador_da_vez(), "ana@CIC")

        host.avancar_turno()
        host.remover_jogador("carol@CIC")
        self.assertEqual(host.jogador_da_vez(), "ana@CIC")

    def test_remove_last_player_finishes_host_game(self):
        host = GameHost("alice@CIC", "banana")
        host.adicionar_jogador("bob@CIC")
        host.iniciar()

        assert host.remover_jogador("bob@CIC")
        self.assertFalse(host.jogadores)
        self.assertEqual(host.estado, "FINISHED")


class AppCompletionTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.config = {
            "name": "alice",
            "namespace": "CIC",
            "lives": 6,
            "max_players": 4,
            "turn_timeout": 30,
        }
        self.app = P2PForcaApp(self.config, self.table)
        self.sent = []
        self.app.enviar = lambda peer_id, message: self.sent.append((peer_id, message))

    def test_cli_peer_and_connection_views(self):
        self.table.peers["bob@CIC"] = self.table._novo(
            "bob@CIC", "127.0.0.1", 8081
        )
        self.table.atualizar_estado("bob@CIC", Estado.CONNECTED)
        peers = self.app.listar_peers("")
        self.assertEqual(peers[0]["peer_id"], "bob@CIC")

        fake_socket = object()
        peer = self.table.peers["bob@CIC"]
        peer["conexao"] = fake_socket
        peer["direcao"] = "outbound"
        peer["rtt"] = 0.045

        conexoes = self.app.listar_conexoes()
        self.assertEqual(conexoes[0]["peer_id"], "bob@CIC")
        rtt = self.app.listar_rtt()
        self.assertEqual(rtt[0]["peer_id"], "bob@CIC")

    def test_log_level_validation(self):
        ok, nivel = self.app.definir_log_level("debug")
        self.assertTrue(ok)
        self.assertEqual(nivel, "DEBUG")

        ok, nivel = self.app.definir_log_level("trace")
        self.assertFalse(ok)
        self.assertIn("inválido", nivel)

    def test_join_running_existing_player_returns_rejoin_and_state(self):
        assert self.app.criar("banana")[0]
        self.app.host.adicionar_jogador("bob@CIC")
        self.app.host.iniciar()

        message = {
            "type": "JOIN",
            "msg_id": "join-1",
            "game_id": self.app.host.game_id,
        }
        self.app.handler(message, "bob@CIC", self.config, self.table)

        join_ok = next(
            message for _, message in self.sent
            if message["type"] == "JOIN_OK"
        )
        self.assertTrue(join_ok["rejoin"])

        states = [
            message for _, message in self.sent
            if message["type"] == "STATE"
        ]
        self.assertTrue(states)
        self.assertEqual(states[-1]["seq"], 1)

    def test_clean_shutdown_host_sends_game_over(self):
        assert self.app.criar("banana")[0]
        self.app.host.adicionar_jogador("bob@CIC")
        self.app.host.iniciar()

        assert self.app.encerramento_limpo()
        game_overs = [
            message for _, message in self.sent
            if message["type"] == "GAME_OVER"
        ]
        self.assertTrue(game_overs)
        self.assertEqual(game_overs[0]["result"], "ABORTED")
        self.assertIsNone(self.app.host)


if __name__ == "__main__":
    unittest.main()
