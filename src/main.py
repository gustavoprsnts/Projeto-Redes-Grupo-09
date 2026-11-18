import logging
import signal
import sys
import threading

from conections.keep_alive import loop_keepalive
from conections.p2p_client import peer_client
from conections.peer_connection import encerrar_conexao, iniciar_servidor
from conections.peer_table import PeerTable
from conections.rendezvous_connection import carrega_json, refresh_register, register, unregister


def configurar_logging(config):
    handlers = [logging.StreamHandler()]
    log_file = config.get("log_file")
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
    )


def main():
    config = carrega_json()
    configurar_logging(config)
    logger = logging.getLogger(__name__)

    meu_id = f"{config['name']}@{config['namespace']}"
    tabela = PeerTable(
        meu_id=meu_id,
        max_tentativas=config["max_reconnect_attempts"],
        base_backoff=config["base_backoff"],
        max_backoff=config["max_backoff"],
    )
    encerrar = threading.Event()
    servidor_sock = None

    def solicitar_encerramento(*_args):
        if not encerrar.is_set():
            logger.info("Sinal de encerramento recebido")
            encerrar.set()

    signal.signal(signal.SIGINT, solicitar_encerramento)
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, solicitar_encerramento)
        except (OSError, ValueError):
            logger.debug("Não foi possível registrar handler para SIGTERM neste ambiente")

    try:
        resposta = register(config)
        if resposta is None:
            logger.error("Não foi possível registrar no Rendezvous; encerrando.")
            return 1

        ttl = resposta.get("ttl", config.get("register_ttl", 7200))
        logger.info("Peer iniciado como %s (ttl=%s)", meu_id, ttl)

        servidor_sock = iniciar_servidor(config, tabela)

        threading.Thread(
            target=peer_client,
            args=(config, tabela, encerrar),
            daemon=True,
            name="peer-client",
        ).start()
        threading.Thread(
            target=refresh_register,
            args=(config, encerrar, ttl),
            daemon=True,
            name="rdv-refresh",
        ).start()
        threading.Thread(
            target=loop_keepalive,
            args=(config, tabela, encerrar),
            daemon=True,
            name="keep-alive",
        ).start()

        logger.info("Peer em execução. Pressione Ctrl+C para encerrar.")
        while not encerrar.wait(1):
            pass

    except KeyboardInterrupt:
        solicitar_encerramento()
    except Exception:
        logger.exception("Erro fatal na execução do peer")
        return 1
    finally:
        encerrar.set()

        if servidor_sock is not None:
            try:
                servidor_sock.close()
            except Exception:
                logger.exception("Falha ao fechar socket do servidor de peers")

        for peer_id, conexao in tabela.coletar_conexoes_ativas():
            try:
                encerrar_conexao(conexao, config, peer_id, "shutdown")
            except Exception:
                logger.exception("Falha ao encerrar conexão com %s durante shutdown", peer_id)

        try:
            unregister(config)
        except Exception:
            logger.exception("Falha ao fazer UNREGISTER no Rendezvous")

        logger.info("Encerramento concluído")

    return 0


if __name__ == "__main__":
    sys.exit(main())