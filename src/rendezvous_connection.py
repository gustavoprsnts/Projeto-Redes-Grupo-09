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

    # json do register 
    mensagem={
        "type": "REGISTER",
        "namespace": config["namespace"],
        "name": config["name"],
        "port": config["listen_port"]
         
    }

    # Realizando conexao tcp 
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # setando timout do tcp em 5 segundos 
    tcp.settimeout(5)
    # usando o try para pegar as excecoes 
    try:
        tcp.connect((host,porta))

        with  tcp.makefile('rw',encoding='UTF-8') as arquivo_socket:
            arquivo_socket.write(json.dumps(mensagem) + "\n")
            arquivo_socket.flush()

    #Leitura da linha json da resposta ao Register 
            linha_resposta = arquivo_socket.readline()

            if linha_resposta:
                resposta = json.loads(linha_resposta.strip())
                if resposta.get("status") == "OK":
                    print(f"Registro realizado com sucesso! IP público detectado: {resposta.get('ip')}")
                    return resposta
                else:
                    print(f"Erro retornado pelo Rendezvous: {resposta.get('message')}")
            else:
                print("Nenhuma resposta recebida do servidor.")
            

    except socket.timeout:
        print("Timeout error")

    except OSError as erro:
        print(f"Erro ao conectar: {erro}")
    finally:
        tcp.close()

if __name__ == "__main__":
    print("A tentar registar no servidor Rendezvous...")
    registrar_no_rdv()




