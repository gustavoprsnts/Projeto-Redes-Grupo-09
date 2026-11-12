import json
import socket
from rendezvous_connection import carrega_json, ler_linha
import threading


# Faz o handshake com o peer que acabou de se conectar
def handshake(conexao, endereco, config):
    try:
        conexao.settimeout(5)
        linha = ler_linha(conexao)
#
        if not linha:
            print("Peer não enviou nenhuma mensagem")
            conexao.close()
            return
        mensagem = json.loads(linha)

      # verificacoes do handshake
        if mensagem.get("type") != "HELLO":
            print("[Erro]  bad_request")
            conexao.close()
            return

        if not mensagem.get("msg_id") or not mensagem.get("peer_id") or mensagem.get("ttl") != 1:
            print("[Erro] bad_request")
            conexao.close()
            return

        if mensagem.get("version") != "1.0":
            print("[Erro] bad_request")
            conexao.close()
            return

        # verifica se o peer tem a feature da forca e guarda na variavel com_hang
        com_hang = "hangman" in mensagem.get("features", [])
        if not com_hang:
            print("peer nao apresenta forca")

        # payload hello_ok
        resposta = {
            "type": "HELLO_OK",
            "msg_id": mensagem["msg_id"],
            "peer_id": config["name"] + "@" + config["namespace"],
            "version": "1.0",
            "features": ["hangman"],
            "ttl": 1
        }

        conexao.sendall((json.dumps(resposta) + '\n').encode("UTF-8"))

        # tira o timeout para abrir a conexão
        conexao.settimeout(None)
        print(f"Handshake realizado com {mensagem['peer_id']}:{endereco}")
        # retorno de dicionario com os dados do peer
        return {
            "peer_id": mensagem["peer_id"],
            "tem_hangman": com_hang,
            "direcao": "inbound"
        }

    except json.JSONDecodeError:
        print("[Erro] bad_json")
        conexao.close()
    except Exception as erro:
        print(f"[Erro] {erro}")
        conexao.close()


def conexao_peer(conexao,endereco,config):
    peer = handshake(conexao,endereco,config)
    if not peer:
        return None
    return peer

 # funcao com o loop para lidar com a aceitação de conexoes dos peers
def loop_accept(socket, config):
    while True:
        conexao, endereco = socket.accept()
        # thread para evitar um processo de conexao atrasar o outro
        t = threading.Thread(target=conexao_peer, args=(
            conexao, endereco, config), daemon=True)
        t.start()


# funcao que inicia conexao que sera usada nos peers
def iniciar_servidor():
    config = carrega_json()
    # criacao de socket tcp
    socketTcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # permite reusar a porta logo após reiniciar o programa
    socketTcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # liga socket a porta usada e o 0.0.0.0 permite a conexao com qualquer interface
    socketTcp.bind(('0.0.0.0', config["listen_port"]))
    # listen prepara socket para receber conexoes
    socketTcp.listen()
    # thread para rodar as funcoes sem travar o programa principal
    thread = threading.Thread(
        target=loop_accept, args=(socketTcp, config), daemon=True)
    thread.start()
    return socketTcp


if __name__ == "__main__":
    iniciar_servidor()
    input("Servidor ligado. Enter para sair.\n")
