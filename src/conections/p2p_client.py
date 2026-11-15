

import threading

from conections.peer_connection import conectar_e_registrar, encerrar_conexao
from conections.rendezvous_connection import discover

# funcao que sincroniza o Randezvous com a Peertable 
def peer_client(config,tabela, encerrar ):
   
    while True:
        lista = discover(config)
        if lista is not None:
            conectar,fechar = tabela.reconcilar(lista) 
            for peer_id, conexao in fechar:
                    threading.Thread(target=encerrar_conexao,
                                    args=(conexao, config, peer_id, "gone"), daemon=True).start()
            for peer_id, ip, porta in conectar:
                    threading.Thread(target=conectar_e_registrar,
                                    args=(peer_id, ip, porta, config, tabela), daemon=True).start()
            if encerrar.wait(config["discover_interval"]):     
                break





