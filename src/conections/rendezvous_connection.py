import json
import logging
import socket
import weakref
from pathlib import Path


logger = logging.getLogger(__name__)

# constante que salva o caminho para acessar config
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"

MAX_BUFFER = 32768
SOBRAS = weakref.WeakKeyDictionary()

# funcao para a leitura e retorno dos dados do arquivo config.json
def carrega_json():
    with open(CONFIG_PATH, "r", encoding="UTF-8") as arquivo:
        dados = json.load(arquivo)
    return dados


# funcao para a leitura de dados ate a quebra de linha
def ler_linha(sock):
    # definicao de buffer
    buffer = SOBRAS.pop(sock, b"")

    # loop para leitura ate encontrar quebra de linha
    try:
        while b"\n" not in buffer:
            parte = sock.recv(2048)
            if not parte:
                break
            buffer += parte

            if len(buffer) > MAX_BUFFER:
                # verificacao do estouro de buffer
                raise ValueError("buffer maior que o limite")
    except BaseException:
        SOBRAS[sock] = buffer
        raise
    if b"\n" not in buffer:
        return buffer
    linha, resto = buffer.split(b"\n", 1)
    if resto:
        SOBRAS[sock] = resto
    return linha
            

    
        
# funcao para comunicacao no randezvous
def conectar_rdv(config, payload):
    # carregando dados do json
    host = config["rdv_host"]
    porta = config["rdv_port"]

    # Realizando conexao tcp
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # setando timeout do tcp em 5 segundos
    tcp_socket.settimeout(5)
    # usando o try para pegar as excecoes
    try:
        tcp_socket.connect((host, porta))

        linha_reposta = json.dumps(payload) + "\n"

        # envio dos dados ao servidor
        tcp_socket.sendall(linha_reposta.encode("UTF-8"))

        mensagem_recebida = ler_linha(tcp_socket)

        if not mensagem_recebida:
            logger.error("Falha ao receber dados do servidor Rendezvous (%s:%s)", host, porta)
            return None

        # converte a mensagem json para dicionario
        resposta = json.loads(mensagem_recebida.strip())

        # verificação dos status
        if resposta.get("status") == "OK":
            return resposta

        logger.warning("Erro retornado pelo Rendezvous: %s", resposta.get("message"))
        return None

    except socket.timeout:
        logger.warning("Timeout ao conectar no Rendezvous (%s:%s)", host, porta)
        return None

    except json.JSONDecodeError:
        logger.error("Erro ao interpretar a resposta JSON do Rendezvous")
        return None

    except Exception as erro:
        logger.exception("Erro ao conectar no Rendezvous: %s", erro)
        return None

    finally:
        tcp_socket.close()


# funcao para registrar no randezvous

def register(config):

    payload = {
        "type": "REGISTER",
        "namespace": config["namespace"],
        "name": config["name"],
        "port": config["listen_port"],
        "ttl": config["register_ttl"],
    }

    resposta = conectar_rdv(config, payload)
    if resposta is not None:
        logger.info(
            "[RDV] registered %s@%s as %s:%s (ttl=%s)",
            config["name"],
            config["namespace"],
            resposta.get("ip"),
            resposta.get("port"),
            resposta.get("ttl"),
        )
    return resposta


# funcao para fazer as descobertas dos peers


def discover(config):

    payload = {
        "type": "DISCOVER",
        "namespace": config["namespace"],
    }
    resposta = conectar_rdv(config, payload)
    if resposta is None:
        return None
    # loop para não aparecer meu proprio peer na lista discover
    lista = []
    for p in resposta.get("peers", []):
        if not (p.get("name") == config["name"] and p.get("namespace") == config["namespace"]):
            lista.append(p)

    return lista


# funcao de unregister para o cancelamento de registro
def unregister(config):
    payload = {
        "type": "UNREGISTER",
        "namespace": config["namespace"],
        "name": config["name"],
        "port": config["listen_port"],
    }
    resposta = conectar_rdv(config, payload)
    return resposta


# refresh do peer antes do fim do ttl
def refresh_register(config, encerrar, ttl):
    intervalo = ttl / 2
    while not encerrar.wait(intervalo):
        resposta = register(config)
        if resposta is not None:
            ttl = resposta.get("ttl", ttl)
            intervalo = ttl / 2
        else:
            logger.warning("Falha ao renovar registro no Rendezvous; nova tentativa em %ss", config["discover_interval"])
            intervalo = config["discover_interval"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    logger.info("A tentar registar no servidor Rendezvous...")
    config = carrega_json()
    teste1 = register(config)
    teste = unregister(config)
    logger.info("Resposta do unregister: %s", teste)