import json
import socket

# funcao para a leitura e retorno dos dados do arquivo config.json
def carrega_json():
    with open("config.json", "r", encoding="UTF-8") as arquivo:
        dados = json.load(arquivo)
        arquivo.close()

    return dados

#funcao para registrar  cliente no randevouz 
def resgistrar_no_rdv():
    # carregando dados do json
    config = carrega_json()
    host = config["rdv_host"]
    porta = config["rdv_port"]

    # Realizando conexão tcp 
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # setando timout do tcp em 5 segundos 
    tcp.settimeout(5)
    # usando o try para pegar as exceções 
    try:
        tcp.connect((host,porta))
    except socket.timeout:
        print("Timeout error")

    except OSError as erro:
        print(f"Erro ao conectar: {erro}")
    finally:
        tcp.close()
        


