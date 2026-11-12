import socket
from rendezvous_connection import carrega_json
import threading




# funcao com o loop para lidar com a aceitação de conexoes dos peers 
def loop_accept(socket):
    while True:
            conexao, endereco = socket.accept()
            print(f"Conexão realizada:{endereco}")

# funcao que inicia conexao que sera usada nos peers 
def iniciar_servidor():
    config = carrega_json()
    # criacao de socket tcp 
    socketTcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # permite reusar a porta logo após reiniciar o programa 
    socketTcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    # liga socket a porta usada e o 0.0.0.0 permite a conexao com qualquer interface 
    socketTcp.bind(('0.0.0.0', config["listen_port"]))
    # listen prepara socket para receber conexoes 
    socketTcp.listen()
    # thread para rodar as funcoes sem travar o programa principal 
    thread = threading.Thread( target= loop_accept, args= (socketTcp,) , daemon= True )
    thread.start() 
    return socketTcp

