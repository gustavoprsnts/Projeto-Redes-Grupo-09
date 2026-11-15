import json
import socket
import uuid
from rendezvous_connection import carrega_json, ler_linha
import threading


# Faz o handshake com o peer que acabou de se conectar
def handshake(conexao, endereco, config):
    try:
        conexao.settimeout(5)
        linha = ler_linha(conexao)
#
        if not linha:
            raise ValueError("Peer não enviou nenhuma mensagem")
        mensagem = json.loads(linha)

      # verificacoes do handshake
        if mensagem.get("type") != "HELLO":
            raise ValueError("[Erro]  bad_request")
           
        if not mensagem.get("msg_id") or not mensagem.get("peer_id") or mensagem.get("ttl") != 1:
            raise ValueError("[Erro] bad_request")
        if mensagem.get("version") != "1.0":
            raise ValueError("[Erro] bad_request")
            

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

# funcao para guardar o id do peer 
def meu_id(config): return config["name"] + "@" + config["namespace"]


#funcao que inicia a conexão e envia o pacote inicial HELLO
def handshake_saida(ip, porta, peer_id_esperado, config):
    conexao = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conexao.settimeout(5)
    try:
        conexao.connect((ip, porta))

        msg_id = str(uuid.uuid4())
        hello = {
            "type": "HELLO",
            "msg_id": msg_id,
            "peer_id": meu_id(config),
            "version": "1.0",
            "features": ["hangman"],
            "ttl": 1
        }
        conexao.sendall((json.dumps(hello) + '\n').encode("UTF-8"))

        linha = ler_linha(conexao)
        if not linha:
            print("peer fechou sem responder o HELLO")
        resposta = json.loads(linha)

        if resposta.get("type") != "HELLO_OK":
            print("resposta nao foi HELLO_OK")
        if resposta.get("msg_id") != msg_id:
            print("msg_id diferente do HELLO")
        if resposta.get("version") != "1.0" or resposta.get("ttl") != 1:
            print("versao ou ttl invalido")
        if resposta.get("peer_id") != peer_id_esperado:
            print("peer_id inesperado")

        com_hang = "hangman" in resposta.get("features", [])
        if not com_hang:
            print("peer nao apresenta forca")

        conexao.settimeout(None)
        print(f"Handshake realizado com {peer_id_esperado}:{ip}")
        return {
            "conexao": conexao,
            "peer_id": peer_id_esperado,
            "tem_hangman": com_hang,
            "direcao": "outbound"
        }

    except Exception as erro:
        print(f"[Erro] handshake de saida com {peer_id_esperado}: {erro}")
        conexao.close()
        return None


# funcao que envia o bye do bye bye_ok 
def encerrar_conexao(conexao, config, peer_id, motivo):
    try:
        bye = {
            "type": "BYE",
            "msg_id": str(uuid.uuid4()),
            "src": meu_id(config),
            "dst": peer_id,
            "reason": motivo,
            "ttl": 1
        }
        conexao.sendall((json.dumps(bye) + '\n').encode("UTF-8"))
        conexao.settimeout(2)          
        ler_linha(conexao)
    except Exception:
        pass
    finally:
        conexao.close()


# funcao que armazena peer conectado no peertable
def guardar_conexao(tabela, config, peer, conexao):
    peer_id = peer["peer_id"]
    venceu, perdedora = tabela.registrar_conexao(
        peer_id, conexao, peer["direcao"], peer["tem_hangman"])

    if perdedora is not None:
        print(f"[PeerServer] Duplicate connection with {peer_id} - "
              f"keeping {tabela.direcao(peer_id)} ")
        encerrar_conexao(perdedora, config, peer_id, "duplicate")


# funcao que coordena a parte do envio do Hello 
def conectar_e_registrar(peer_id, ip, porta, config, tabela):
    resultado = handshake_saida(ip, porta, peer_id, config)
    if resultado is None:
        tabela.registra_erro(peer_id)
        return
    guardar_conexao(tabela, config, resultado, resultado["conexao"])

#funcao que coordena a parte de chegada do handshake
def conexao_peer(conexao,endereco,config,tabela):
    peer = handshake(conexao,endereco,config)
    if not peer:
        return None
    guardar_conexao(tabela, config, peer, conexao)

 # funcao com o loop para lidar com a aceitação de conexoes dos peers
def loop_accept(sock, config, tabela):
    while True:
        conexao, endereco = sock.accept()
        # thread para evitar um processo de conexao atrasar o outro
        t = threading.Thread(target=conexao_peer, args=(
            conexao, endereco, config,tabela), daemon=True)
        t.start()

# funcao que inicia conexao que sera usada nos peers
def iniciar_servidor(config, tabela):
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
        target=loop_accept, args=(socketTcp, config,tabela), daemon=True)
    thread.start()
    return socketTcp





