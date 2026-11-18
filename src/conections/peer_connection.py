import json
import logging
import socket
import threading
import uuid

from conections.peer_table import Estado
from conections.protocolo import (
    ENDERECO_OPCIONAL,
    OBRIGATORIOS,
    SEM_ENDERECO,
    criar_envelope,
)
from conections.rendezvous_connection import ler_linha


logger = logging.getLogger(__name__)


# funcao para guardar o id do peer
def meu_id(config):
    return config["name"] + "@" + config["namespace"]


def enviar_json(conexao, msg):
    dados = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
    logger.debug("TX %s", json.dumps(msg, ensure_ascii=False, sort_keys=True))
    conexao.sendall(dados)


def enviar_para_peer(tabela, peer_id, msg):
    conexao = tabela.obter(peer_id, "conexao")
    if conexao is None:
        raise ConnectionError(f"Peer {peer_id} não está conectado")
    enviar_json(conexao, msg)
    return True


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

        enviar_json(conexao, resposta)

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
        try:
            conexao.close()
        except Exception:
            pass
        return None
    except Exception as erro:
        logger.exception("Erro no handshake de entrada com %s: %s", endereco, erro)
        try:
            conexao.close()
        except Exception:
            pass
        return None


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
        enviar_json(conexao, hello)

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
        bye = criar_envelope(
            "BYE",
            src=meu_id(config),
            dst=peer_id,
            msg_id=str(uuid.uuid4()),
            reason=motivo,
        )
        enviar_json(conexao, bye)
        try:
            conexao.settimeout(2)
            ler_linha(conexao)
        except Exception:
            pass
    except Exception as erro:
        logger.debug("Falha ao encerrar conexão com %s (%s): %s", peer_id, motivo, erro)
    finally:
        try:
            conexao.close()
        except Exception:
            pass


def _processar_mensagem_recebida(msg, peer_id, conexao, config, tabela, handler_jogo=None):
    tipo = msg.get("type")
    meu = meu_id(config)

    if msg.get("ttl") != 1:
        resposta = criar_envelope(
            "ERROR", src=meu, dst=peer_id,
            ref_msg_id=msg.get("msg_id"),
            code="bad_request",
            message="ttl must be 1",
        )
        enviar_json(conexao, resposta)
        return "ok"

    if tipo not in SEM_ENDERECO and tipo not in ENDERECO_OPCIONAL:
        if msg.get("dst") != meu:
            resposta = criar_envelope(
                "ERROR", src=meu, dst=peer_id,
                ref_msg_id=msg.get("msg_id"),
                code="not_for_me",
                message="destination does not match local peer",
            )
            enviar_json(conexao, resposta)
            return "ok"

    if tipo not in OBRIGATORIOS:
        resposta = criar_envelope(
            "ERROR", src=meu, dst=peer_id,
            ref_msg_id=msg.get("msg_id"),
            code="unknown_type",
            message=f"unknown type: {tipo}",
        )
        enviar_json(conexao, resposta)
        return "ok"

    if tipo == "PING":
        resposta = criar_envelope(
            "PONG",
            src=meu,
            dst=peer_id,
            msg_id=msg.get("msg_id"),
            timestamp=msg.get("timestamp"),
        )
        enviar_json(conexao, resposta)
        return "ok"

    if tipo == "PONG":
        rtt = tabela.registrar_pong(peer_id, conexao, msg.get("msg_id"))
        if rtt is not None:
            logger.debug("PONG recebido de %s (rtt=%.3fs)", peer_id, rtt)
        else:
            logger.debug("PONG recebido de %s", peer_id)
        return "ok"

    if tipo == "BYE":
        try:
            resposta = criar_envelope(
                "BYE_OK",
                src=meu,
                dst=peer_id,
                msg_id=msg.get("msg_id"),
            )
            enviar_json(conexao, resposta)
        except Exception as erro:
            logger.debug("Falha ao enviar BYE_OK para %s: %s", peer_id, erro)
        logger.info("BYE recebido de %s (reason=%s)", peer_id, msg.get("reason"))
        return "bye"

    if tipo in {"BYE_OK", "ERROR", "HELLO", "HELLO_OK"}:
        logger.debug("Mensagem de controle recebida de %s: type=%s", peer_id, tipo)
        return "ok"

    if handler_jogo is not None:
        try:
            handler_jogo(msg, peer_id, config, tabela)
        except Exception:
            logger.exception("Erro no handler de jogo ao processar mensagem de %s (type=%s)", peer_id, tipo)
        return "ok"

    logger.info("Mensagem recebida de %s (sem handler de jogo): type=%s", peer_id, tipo)
    return "ok"


def loop_receber(conexao, peer_id, config, tabela, handler_jogo=None):
    logger.info("Iniciando loop de recepção para %s", peer_id)
    motivo_estado = Estado.STALE
    try:
        while True:
            try:
                linha = ler_linha(conexao)
            except (ConnectionAbortedError, ConnectionResetError, OSError) as erro:
                logger.info("Conexão com %s encerrada durante leitura: %s", peer_id, erro)
                break
            except ValueError as erro:
                logger.warning("Erro de framing com %s: %s", peer_id, erro)
                break

            if not linha:
                logger.info("Conexão com %s fechada pelo peer", peer_id)
                break

            try:
                msg = json.loads(linha)
            except json.JSONDecodeError:
                logger.warning("Mensagem JSON inválida recebida de %s", peer_id)
                try:
                    erro = criar_envelope(
                        "ERROR",
                        src=meu_id(config),
                        dst=peer_id,
                        code="bad_json",
                        message="invalid JSON",
                    )
                    enviar_json(conexao, erro)
                except Exception:
                    pass
                break

            if not isinstance(msg, dict):
                logger.warning("Mensagem inválida recebida de %s (não é objeto JSON)", peer_id)
                continue

            logger.debug("RX %s %s", peer_id, json.dumps(msg, ensure_ascii=False, sort_keys=True))

            tabela.registrar_atividade(peer_id, conexao)

            try:
                resultado = _processar_mensagem_recebida(msg, peer_id, conexao, config, tabela, handler_jogo=handler_jogo)
            except Exception:
                logger.exception("Erro ao processar mensagem de %s: %s", peer_id, msg.get("type"))
                continue

            if resultado == "bye":
                motivo_estado = Estado.GONE
                break
    finally:
        removida = tabela.desconectar_conexao(peer_id, conexao, novo_status=motivo_estado)
        try:
            conexao.close()
        except Exception:
            pass
        if handler_jogo is not None:
            try:
                handler_jogo(
                    {"type": "PEER_DOWN", "peer_id": peer_id, "ttl": 1},
                    peer_id,
                    config,
                    tabela,
                )
            except Exception:
                logger.exception("Erro no handler de jogo ao processar queda de %s", peer_id)
        if removida:
            logger.info("Conexão com %s removida da tabela (estado=%s)", peer_id, motivo_estado.value)
        else:
            logger.debug("Conexão encerrada para %s, mas já não era a conexão ativa na tabela", peer_id)


# funcao que armazena peer conectado no peertable
def guardar_conexao(tabela, config, peer, conexao, handler_jogo=None):
    peer_id = peer["peer_id"]
    venceu, perdedora = tabela.registrar_conexao(
        peer_id, conexao, peer["direcao"], peer["tem_hangman"]
    )

    if not venceu:
        logger.info("Conexão de entrada/saída com %s rejeitada por duplicata; encerrando", peer_id)
        encerrar_conexao(conexao, config, peer_id, "duplicate")
        return False

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

    threading.Thread(
        target=loop_receber,
        args=(conexao, peer_id, config, tabela, handler_jogo),
        daemon=True,
        name=f"rx-{peer_id}",
    ).start()
    return True


# funcao que coordena a parte do envio do Hello
def conectar_e_registrar(peer_id, ip, porta, config, tabela, handler_jogo=None):
    resultado = handshake_saida(ip, porta, peer_id, config)
    if resultado is None:
        tabela.registra_erro(peer_id)
        return
    guardar_conexao(tabela, config, resultado, resultado["conexao"], handler_jogo=handler_jogo)


# funcao que coordena a parte de chegada do handshake
def conexao_peer(conexao, endereco, config, tabela, handler_jogo=None):
    peer = handshake(conexao, endereco, config)
    if not peer:
        return None
    guardar_conexao(tabela, config, peer, conexao, handler_jogo=handler_jogo)
    return peer


# funcao com o loop para lidar com a aceitação de conexoes dos peers
def loop_accept(sock, config, tabela, handler_jogo=None):
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
        t = threading.Thread(
            target=conexao_peer,
            args=(conexao, endereco, config, tabela, handler_jogo),
            daemon=True,
        )
        t.start()


# funcao que inicia conexao que sera usada nos peers
def iniciar_servidor(config, tabela, handler_jogo=None):
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
        target=loop_accept, args=(socketTcp, config, tabela, handler_jogo), daemon=True
    )
    thread.start()
    return socketTcp
