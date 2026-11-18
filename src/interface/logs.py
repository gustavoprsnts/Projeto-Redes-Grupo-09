import logging
import sys

TAGS_ESPECIFICACAO = {"RDV", "PeerServer", "KeepAlive", "Host", "Player", "Game"}
FORMATO = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_console = None
MAPA = {
    "conections.rendezvous_connection": "RDV",
    "conections.peer_connection": "PeerServer",
    "conections.peer_table": "PeerServer",
    "conections.p2p_client": "PeerServer",
    "conections.keep_alive": "KeepAlive",
    "forcaAPP": "Game", "src.forcaAPP": "Game",
    "__main__": "CLI", "interface.cli": "CLI",
}

# classe 
class FiltroMensagem(logging.Filter):
     #funcao para filtrar mensagens de log 
   def filter(self, record):
        tag = MAPA.get(record.name)
        if tag not in {"RDV", "CLI"}:
            return False
        record.name = tag
        return record.levelno >= logging.INFO                               



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