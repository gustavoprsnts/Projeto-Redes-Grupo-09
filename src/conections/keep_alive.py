import logging
import time

from conections.peer_connection import encerrar_conexao, enviar_json, meu_id
from conections.protocolo import agora_iso, criar_envelope


logger = logging.getLogger(__name__)


def _enviar_ping(peer_id, conexao, config, tabela):
    msg = criar_envelope("PING", timestamp=agora_iso())
    try:
        enviar_json(conexao, msg)
        if tabela.registrar_ping_enviado(peer_id, conexao, msg.get("msg_id")):
            logger.debug("PING enviado para %s (msg_id=%s)", peer_id, msg.get("msg_id"))
            return True
    except Exception as erro:
        logger.warning("Falha ao enviar PING para %s: %s", peer_id, erro)
    return False


def loop_keepalive(config, tabela, encerrar):
    ping_interval = float(config.get("ping_interval", 30))
    ping_miss_limit = int(config.get("ping_miss_limit", 3))
    timeout_pong = float(config.get("ping_timeout", min(ping_interval, 5)))
    tick = min(1.0, max(0.2, ping_interval / 2))

    logger.info( "Iniciando keep-alive (intervalo=%ss, limite_falhas=%s, timeout_pong=%ss)",ping_interval,ping_miss_limit,timeout_pong,)

    while not encerrar.is_set():
        try:
            agora = time.time()
            for peer_id, conexao in tabela.obter_conexoes_para_keepalive():
                estado = tabela.estado_keepalive(peer_id)
                if not estado or estado.get("conexao") is not conexao:
                    continue

                pendente = estado.get("ping_pendente")
                ultimo_envio = estado.get("ultimo_ping_envio")

                if pendente is not None and ultimo_envio is not None:
                    if (agora - ultimo_envio) >= timeout_pong:
                        falhas = tabela.registrar_falha_ping(peer_id, conexao)
                        if falhas is None:
                            continue
                        logger.warning(
                            "Timeout de PONG de %s (falhas=%d/%d)", peer_id, falhas, ping_miss_limit
                        )
                        if falhas >= ping_miss_limit:
                            logger.info("Encerrando conexão com %s por excesso de falhas de keep-alive", peer_id)
                            try:
                                encerrar_conexao(conexao, config, peer_id, "ping_timeout")
                            finally:
                                tabela.desconectar_conexao(peer_id, conexao)
                    continue

                if ultimo_envio is None or (agora - ultimo_envio) >= ping_interval:
                    _enviar_ping(peer_id, conexao, config, tabela)

        except Exception:
            logger.exception("Erro no loop de keep-alive")

        if encerrar.wait(tick):
            break

    logger.info("Loop de keep-alive encerrado")
