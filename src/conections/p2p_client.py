import logging
import threading

from conections.peer_connection import conectar_e_registrar, encerrar_conexao
from conections.rendezvous_connection import discover


logger = logging.getLogger(__name__)


# funcao que sincroniza o Randezvous com a Peertable
def peer_client(config, tabela, encerrar, handler_jogo=None):
    logger.info("Iniciando loop de descoberta de peers (intervalo=%ss)", config.get("discover_interval"))
    while not encerrar.is_set():
        try:
            lista = discover(config)
            if lista is None:
                logger.warning("Falha ao descobrir peers no Rendezvous; nova tentativa no próximo ciclo")
            else:
                conectar, fechar = tabela.reconciliar(lista)
                if conectar or fechar:
                    logger.info(
                        "Reconciliação de peers: %d para conectar, %d para fechar",
                        len(conectar),
                        len(fechar),
                    )
                for peer_id, conexao in fechar:
                    threading.Thread(
                        target=encerrar_conexao,
                        args=(conexao, config, peer_id, "gone"),
                        daemon=True,
                    ).start()
                for peer_id, ip, porta in conectar:
                    threading.Thread(
                        target=conectar_e_registrar,
                        args=(peer_id, ip, porta, config, tabela, handler_jogo),
                        daemon=True,
                    ).start()
        except Exception:
            logger.exception("Erro no ciclo de descoberta/reconciliação de peers")

        if encerrar.wait(config.get("discover_interval", 20)):
            break

    logger.info("Loop de descoberta de peers encerrado")
