# Cabeçalho 
# Alunos 
#  Arthur Correia Marques — 241022316
# - Gustavo Pires dos Santos — 251004349
# - Helton Rodrigues da Silva Junior — 251021789

import logging
import signal
import sys
import threading

from conections.keep_alive import loop_keepalive
from conections.p2p_client import peer_client
from conections.peer_connection import encerrar_conexao, iniciar_servidor
from conections.peer_table import PeerTable
from conections.rendezvous_connection import carrega_json, refresh_register, register, unregister
from game.forcaAPP import P2PForcaApp
from interface.cli import CLI
from interface.logs import configurar_logging

# funcao dedicada ao loop principal do projeto 
def main():
    config = carrega_json()
    configurar_logging(config.get("log_file"), "INFO")
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
    app = P2PForcaApp(config, tabela)

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

        servidor_sock = iniciar_servidor(config, tabela, app.handler)

        threading.Thread(
            target=peer_client,
            args=(config, tabela, encerrar, app.handler),
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
        threading.Thread(
            target=CLI(app, encerrar).run,
            daemon=True,
            name="cli",
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

        try:
            app.encerramento_limpo()
        except Exception:
            logger.exception("Falha ao enviar LEAVE ou GAME_OVER antes do encerramento")

        for peer_id, conexao in tabela.coletar_conexoes_ativas():
            try:
                encerrar_conexao(conexao, config, peer_id, "shutdown")
            except Exception:
                logger.exception("Falha ao encerrar conexão com %s durante shutdown", peer_id)

        if servidor_sock is not None:
            try:
                servidor_sock.close()
            except Exception:
                logger.exception("Falha ao fechar socket do servidor de peers")

        try:
            unregister(config)
        except Exception:
            logger.exception("Falha ao fazer UNREGISTER no Rendezvous")

        logger.info("Encerramento concluído")

    return 0


if __name__ == "__main__":
    sys.exit(main())