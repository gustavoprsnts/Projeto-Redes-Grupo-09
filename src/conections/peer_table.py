from enum import Enum
import threading
import time 
# Enum que representa os estados do peer
class Estado(Enum):
    DISCOVERED = "DISCOVERED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    STALE = "STALE"
    GONE = "GONE"


# classe para representação da tabela de peers 

class PeerTable:
    def __init__(self, meu_id, max_tentativas, base_backoff, max_backoff):
        self.peers = {}
        self.lock = threading.Lock()
        self.meu_id = meu_id
        self.max_tentativas = max_tentativas
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff

    def _novo(self, peer_id, ip=None, port=None):
        return {
            "peer_id": peer_id,
            "status": Estado.DISCOVERED,
            "conexao": None,
            "ip": ip,
            "port": port,
            "direcao": None,
            "rtt": None,
            "tem_hangman": False,
            "tentativas": 0,
            "proxima_tentativa": None,
        }
    
    def direcao(self, peer_id):
        return "outbound" if self.meu_id < peer_id else "inbound"
    
    def remove(self, peer_id):
        with self.lock:
            self.peers.pop(peer_id, None)

    def listar(self):
        with self.lock:
            return list(self.peers.values())

    def obter(self, peer_id):
        with self.lock:
            return self.peers.get(peer_id)
        
    def atualizar_estado(self, peer_id, novo_status):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["status"] = novo_status

# funcao que verifica o erro de conxao de um peer e calcula backoff
    def registra_erro(self,peer_id):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None or peer["conexao"] is not None:
                return
            peer["tentativas"] += 1
            if peer["tentativas"] >= self.max_tentativas:
                peer["status"] = Estado.GONE
                peer["proxima_tentativa"] = None
                return
            espera = min(self.max_backoff, self.base_backoff * 2 ** (peer["tentativas"] - 1))
            peer["proxima_tentativa"] = time.time() + espera
            peer["status"] = Estado.STALE

        
# funcao que olha a mensagem do randezvous e compara com a situação atual na tabela e com isso faz as ateraçoes necessarias
    def reconciliar(self, lista_discover):
        agora = time.time()
        vistos = set()
        para_conectar = []
        para_fechar = []

        with self.lock:
            # pecorre os peers do randezvous 
            for p in lista_discover:
                peer_id = p["name"] + "@" + p["namespace"]
                if peer_id == self.meu_id:
                    continue
                vistos.add(peer_id)
                peer = self.peers.get(peer_id)
                #se o peer for novo, ele é cadastrado 
                if peer is None:
                    self.peers[peer_id] = self._novo(peer_id, p["ip"], p["port"])
                else:
                    peer["ip"] = p["ip"]
                    peer["port"] = p["port"]
                    # se estava como gone volta ao estado DISCOVERED
                    if peer["status"] == Estado.GONE:          
                        peer["status"] = Estado.DISCOVERED
                        peer["tentativas"] = 0
                        peer["proxima_tentativa"] = None

           # loop para verificar quais peers precisam fechar conexao 
            for peer_id, peer in self.peers.items():
                if peer_id not in vistos and peer["status"] != Estado.GONE:
                    if peer["conexao"] is not None:
                        para_fechar.append((peer_id, peer["conexao"]))
                    peer["conexao"] = None
                    peer["direcao"] = None
                    peer["status"] = Estado.GONE

        #loop para ver quais peers precisam conectar 
            for peer_id, peer in self.peers.items():
                pode = peer["proxima_tentativa"] is None or peer["proxima_tentativa"] <= agora
                if (peer["status"] in (Estado.DISCOVERED, Estado.STALE)
                        and peer["conexao"] is None and peer["ip"] and pode):
                    peer["status"] = Estado.CONNECTING         
                    para_conectar.append((peer_id, peer["ip"], peer["port"]))

        return para_conectar, para_fechar
    
#funcao que apresenta a regra e desempate entre os peers 
    def registrar_conexao(self, peer_id, conexao, direcao, tem_hangman):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None:
                peer = self._novo(peer_id)
                self.peers[peer_id] = peer

            antiga = peer["conexao"]
            if antiga is None:
                nova_vence = True
            else:
                manter = self.direcao(peer_id)
                if direcao == manter:
                    nova_vence = True
                elif peer["direcao"] == manter:
                    nova_vence = False
                else:
                    nova_vence = True      

            if not nova_vence:
                return False, conexao

            peer["conexao"] = conexao
            peer["direcao"] = direcao
            peer["tem_hangman"] = tem_hangman
            peer["status"] = Estado.CONNECTED
            peer["tentativas"] = 0
            peer["proxima_tentativa"] = None
            return True, antiga