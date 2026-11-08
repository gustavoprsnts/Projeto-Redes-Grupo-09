import json
import socket

# funcao para a leitura e retorno dos dados do arquivo config.json


def carrega_json():
    with open("config.json", "r", encoding="UTF-8") as arquivo:
        dados = json.load(arquivo)
        arquivo.close()

    return dados


config = carrega_json()
# funcao para comunicacao no randezvous


def conectar_rdv(config, payload):
    # carregando dados do json
    host = config["rdv_host"]
    porta = config["rdv_port"]

    # Realizando conexao tcp
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # setando timout do tcp em 5 segundos
    tcp_socket.settimeout(5)
    # usando o try para pegar as excecoes
    try:
        # criacao do socket tcp
        tcp_socket.connect((host, porta))

        # Conversao da mensagem em um json + quebra de linha
        linha_reposta = json.dumps(payload) + '\n'

        # envio dos dados ao servidor
        tcp_socket.sendall(linha_reposta.encode('UTF-8'))

        # Guarda mensagem recebida do servidor
        mensagem_recebida = tcp_socket.recv(32768)

        # converte a mensagem json para dicionario
        resposta = json.loads(mensagem_recebida.strip())

        # verificação dos status
        if resposta.get("status") == "OK":
            return resposta
        else:
            print(f"Erro retornado pelo Rendezvous: {resposta.get('message')}")

    except socket.timeout:
        print("Timeout error")

    except Exception as erro:
        print(f"Erro ao conectar: {erro}")
    except json.JSONDecodeError:
        print("Erro ao interpretar a resposta JSON")
    finally:
        tcp_socket.close()

# funcao para registrar no randezvous


def registrar_no_rdv(config):

    payload = {
        "type": "REGISTER",
        "namespace": config["namespace"],
        "name": config["name"],
        "port": config["listen_port"]
    }

    resposta = conectar_rdv(config, payload)
    return resposta


def descobrir_peers(config):

    payload = {
        "type": "DISCOVER",
        "namespace": config["namespace"]
    }

    resposta = conectar_rdv(config, payload)
    return resposta


def unregister(config):
    payload = {
        "type": "UNREGISTER",
        "namespace": config["namespace"],
        "name": config["name"],
        "port": config["listen_port"]
    }
    resposta = conectar_rdv(config, payload)
    return resposta


if __name__ == "__main__":
    print("A tentar registar no servidor Rendezvous...")
    teste1 = registrar_no_rdv(config)
    teste = unregister(config)
    print(teste)
