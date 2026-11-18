import json
import logging
import socket
import threading
import uuid

from conections.rendezvous_connection import ler_linha


logger = logging.getLogger(__name__)


# Faz o handshake com o peer que acabou de se conectar
def handshake(conexao, endereco, config):
    try:
        conexao.settimeout(5)
        linha = ler_linha(conexao)

        if not linha:
            logger.warning("Peer %s não enviou nenhuma mensagem no handshake", endereco)
            conexao.close()
            return None

        mensagem = json.loads(linha)

        # verificacoes do handshake
        if mensagem.get("type") != "HELLO":
            logger.warning("Handshake inválido de %s: type != HELLO", endereco)
            conexao.close()
            return None
        if not mensagem.get("msg_id") or not mensagem.get("peer_id") or mensagem.get("ttl") != 1:
            logger.warning("Handshake inválido de %s: campos obrigatórios ausentes/ttl inválido", endereco)
            conexao.close()
            return None
        if mensagem.get("version") != "1.0":
            logger.warning("Handshake inválido de %s: versão não suportada (%s)", endereco, mensagem.get("version"))
            conexao.close()
            return None

        # verifica se o peer tem a feature da forca e guarda na variavel com_hang
        com_hang = "hangman" in mensagem.get("features", [])
        if not com_hang:
            logger.info("Peer %s não anuncia suporte a hangman", mensagem.get("peer_id"))

        # payload hello_ok
        resposta = {
            "type": "HELLO_OK",
            "msg_id": mensagem["msg_id"],
            "peer_id": meu_id(config),
            "version": "1.0",
            "features": ["hangman"],
            "ttl": 1,
        }

        conexao.sendall((json.dumps(resposta) + "\n").encode("UTF-8"))

        # tira o timeout para abrir a conexão
        conexao.settimeout(None)
        logger.info("Handshake de entrada realizado com %s (%s)", mensagem["peer_id"], endereco)
        # retorno de dicionario com os dados do peer
        return {
            "peer_id": mensagem["peer_id"],
            "tem_hangman": com_hang,
            "direcao": "inbound",
        }

    except json.JSONDecodeError:
        logger.warning("Erro de handshake com %s: bad_json", endereco)
        conexao.close()
        return None
    except Exception as erro:
        logger.exception("Erro no handshake de entrada com %s: %s", endereco, erro)
        try:
            conexao.close()
        except Exception:
            pass
        return None


# funcao para guardar o id do peer
def meu_id(config):
    return config["name"] + "@" + config["namespace"]


# funcao que inicia a conexão e envia o pacote inicial HELLO
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
            "ttl": 1,
        }
        conexao.sendall((json.dumps(hello) + "\n").encode("UTF-8"))

        linha = ler_linha(conexao)
        if not linha:
            logger.warning("Peer %s (%s:%s) fechou sem responder o HELLO", peer_id_esperado, ip, porta)
            conexao.close()
            return None

        resposta = json.loads(linha)

        if resposta.get("type") != "HELLO_OK":
            logger.warning(
                "Handshake de saída com %s falhou: resposta não foi HELLO_OK (%s)",
                peer_id_esperado,
                resposta.get("type"),
            )
            conexao.close()
            return None
        if resposta.get("msg_id") != msg_id:
            logger.warning("Handshake de saída com %s falhou: msg_id diferente do HELLO", peer_id_esperado)
            conexao.close()
            return None
        if resposta.get("version") != "1.0" or resposta.get("ttl") != 1:
            logger.warning(
                "Handshake de saída com %s falhou: versão/ttl inválidos (version=%s, ttl=%s)",
                peer_id_esperado,
                resposta.get("version"),
                resposta.get("ttl"),
            )
            conexao.close()
            return None
        if resposta.get("peer_id") != peer_id_esperado:
            logger.warning(
                "Handshake de saída falhou: peer_id inesperado (esperado=%s, recebido=%s)",
                peer_id_esperado,
                resposta.get("peer_id"),
            )
            conexao.close()
            return None

        com_hang = "hangman" in resposta.get("features", [])
        if not com_hang:
            logger.info("Peer %s não anuncia suporte a hangman", peer_id_esperado)

        conexao.settimeout(None)
        logger.info("Handshake de saída realizado com %s (%s:%s)", peer_id_esperado, ip, porta)
        return {
            "conexao": conexao,
            "peer_id": peer_id_esperado,
            "tem_hangman": com_hang,
            "direcao": "outbound",
        }

    except Exception as erro:
        logger.exception("Erro no handshake de saída com %s (%s:%s): %s", peer_id_esperado, ip, porta, erro)
        try:
            conexao.close()
        except Exception:
            pass
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
            "ttl": 1,
        }
        conexao.sendall((json.dumps(bye) + "\n").encode("UTF-8"))
        conexao.settimeout(2)
        ler_linha(conexao)
    except Exception as erro:
        logger.debug("Falha ao encerrar conexão com %s (%s): %s", peer_id, motivo, erro)
    finally:
        try:
            conexao.close()
        except Exception:
            pass


# funcao que armazena peer conectado no peertable
def guardar_conexao(tabela, config, peer, conexao):
    peer_id = peer["peer_id"]
    venceu, perdedora = tabela.registrar_conexao(
        peer_id, conexao, peer["direcao"], peer["tem_hangman"]
    )

    if perdedora is not None:
        try:
            direcao_mantida = tabela.direcao(peer_id)
        except Exception:
            direcao_mantida = "desconhecida"
        logger.info(
            "[PeerServer] Conexão duplicada com %s; mantendo %s e encerrando a outra",
            peer_id,
            direcao_mantida,
        )
        encerrar_conexao(perdedora, config, peer_id, "duplicate")


# funcao que coordena a parte do envio do Hello
def conectar_e_registrar(peer_id, ip, porta, config, tabela):
    resultado = handshake_saida(ip, porta, peer_id, config)
    if resultado is None:
        tabela.registra_erro(peer_id)
        return
    guardar_conexao(tabela, config, resultado, resultado["conexao"])


# funcao que coordena a parte de chegada do handshake
def conexao_peer(conexao, endereco, config, tabela):
    peer = handshake(conexao, endereco, config)
    if not peer:
        return None
    guardar_conexao(tabela, config, peer, conexao)
    return peer


# funcao com o loop para lidar com a aceitação de conexoes dos peers
def loop_accept(sock, config, tabela):
    logger.info("Peer server aceitando conexões na porta %s", config.get("listen_port"))
    while True:
        try:
            conexao, endereco = sock.accept()
        except OSError as erro:
            logger.info("Loop de accept encerrado: %s", erro)
            break
        except Exception:
            logger.exception("Erro inesperado no accept do peer server")
            continue

        # thread para evitar um processo de conexao atrasar o outro
        t = threading.Thread(target=conexao_peer,args=(conexao, endereco, config, tabela),daemon=True,)
        t.start()


# funcao que inicia conexao que sera usada nos peers
def iniciar_servidor(config, tabela):
    # criacao de socket tcp
    socketTcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # permite reusar a porta logo após reiniciar o programa
    socketTcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # liga socket a porta usada e o 0.0.0.0 permite a conexao com qualquer interface
    socketTcp.bind(("0.0.0.0", config["listen_port"]))
    # listen prepara socket para receber conexoes
    socketTcp.listen()
    logger.info("Peer server escutando em 0.0.0.0:%s", config["listen_port"])
    # thread para rodar as funcoes sem travar o programa principal
    thread = threading.Thread(
        target=loop_accept, args=(socketTcp, config, tabela), daemon=True
    )
    thread.start()
    return socketTcp
