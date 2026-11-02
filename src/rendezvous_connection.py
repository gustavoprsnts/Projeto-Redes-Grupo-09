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
    #carregando dados do json
    config = carrega_json()
    host = config["rdv_host"]
    porta = config["rdv_port"]
    
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    


