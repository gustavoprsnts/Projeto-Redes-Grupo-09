import logging
import sys

TAGS_ESPECIFICACAO = {"RDV", "PeerServer", "KeepAlive", "Host", "Player", "Game", "CLI"}
FORMATO = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_console = None
MAPA = {
    "conections.rendezvous_connection": "RDV",
    "conections.peer_connection": "PeerServer",
    "conections.peer_table": "PeerServer",
    "conections.p2p_client": "PeerServer",
    "conections.keep_alive": "KeepAlive",
    "game.forcaAPP": "Game", "src.game.forcaAPP": "Game",
    "game.game_host": "Host", "src.game.game_host": "Host",
    "game.game_player": "Player", "src.game.game_player": "Player",
    "game.hangman": "Game", "src.game.hangman": "Game",
    "__main__": "CLI", "main": "CLI", "src.main": "CLI",
    "interface.cli": "CLI", "src.interface.cli": "CLI",
}

# classe 
class FiltroMensagem(logging.Filter):
     #funcao para filtrar mensagens de log 
   def filter(self, record):
        tag = MAPA.get(record.name)
        if tag not in TAGS_ESPECIFICACAO and tag != "CLI":
            return False
        record.name = tag
        return True



#  funcao que configura o sistema de logging global co
def configurar_logging(log_file=None, nivel="INFO"):
    global _console
    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.setLevel(logging.DEBUG)                 
    _console = logging.StreamHandler(sys.stdout)
    _console.setLevel(getattr(logging, nivel.upper()))
    _console.addFilter(FiltroMensagem())
    _console.setFormatter(logging.Formatter(FORMATO))
    raiz.addHandler(_console)
    if log_file:
        arquivo = logging.FileHandler(log_file, encoding="utf-8")
        arquivo.setLevel(logging.DEBUG)         
        arquivo.setFormatter(logging.Formatter(FORMATO))
        raiz.addHandler(arquivo)


def definir_nivel_tela(nome):
    if _console:
        _console.setLevel(getattr(logging, nome.upper()))