import logging
import threading
import time
from enum import Enum


logger = logging.getLogger(__name__)


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
            "ultimo_contato": None,
            "ultimo_ping_envio": None,
            "ping_pendente": None,
            "falhas_ping": 0,
        }
    
    def direcao(self, peer_id):
        return "outbound" if self.meu_id < peer_id else "inbound"
    
    def remove(self, peer_id):
        with self.lock:
            self.peers.pop(peer_id, None)

    def listar(self):
        with self.lock:
            return list(self.peers.values())

#funcao para obter dados dos peers 
    def obter(self, peer_id, campo=None):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None:
                return None
            if campo is None:
                return peer
            return peer.get(campo)
        
    def atualizar_estado(self, peer_id, novo_status):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["status"] = novo_status

# funcao que pecorre a tabela e armazena os peers com conexões ativas 
    def coletar_conexoes_ativas(self):
        with self.lock:
            ativas = []
            for peer_id, peer in self.peers.items():
                if peer.get("conexao") is not None:
                    ativas.append((peer_id, peer["conexao"]))
                    peer["conexao"] = None
                    peer["direcao"] = None
                    peer["status"] = Estado.GONE
                    peer["proxima_tentativa"] = None
            return ativas
 #funcao que remove a conexão da tabela apenas se ela ainda for a conexão ativa do peer.
    def desconectar_conexao(self, peer_id, conexao, novo_status=Estado.STALE):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None or peer.get("conexao") is not conexao:
                return False
            peer["conexao"] = None
            peer["direcao"] = None
            peer["status"] = novo_status
            peer["proxima_tentativa"] = None
            peer["ultimo_ping_envio"] = None
            peer["ping_pendente"] = None
            peer["falhas_ping"] = 0
            return True

    def registrar_atividade(self, peer_id, conexao=None):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None:
                return False
            if conexao is not None and peer.get("conexao") is not conexao:
                return False
            peer["ultimo_contato"] = time.time()
            return True

    def registrar_ping_enviado(self, peer_id, conexao, msg_id):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None or peer.get("conexao") is not conexao or peer.get("status") != Estado.CONNECTED:
                return False
            agora = time.time()
            peer["ultimo_ping_envio"] = agora
            peer["ping_pendente"] = msg_id
            return True

    def registrar_pong(self, peer_id, conexao, msg_id):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None or peer.get("conexao") is not conexao:
                return None
            if peer.get("ping_pendente") is not None and msg_id is not None and peer.get("ping_pendente") != msg_id:
               
                peer["ultimo_contato"] = time.time()
                return None
            agora = time.time()
            rtt = None
            if peer.get("ultimo_ping_envio") is not None:
                rtt = max(0.0, agora - peer["ultimo_ping_envio"])
                peer["rtt"] = rtt
            peer["ultimo_contato"] = agora
            peer["ping_pendente"] = None
            peer["falhas_ping"] = 0
            return rtt

    def obter_conexoes_para_keepalive(self):
        with self.lock:
            itens = []
            for peer_id, peer in self.peers.items():
                if peer.get("status") == Estado.CONNECTED and peer.get("conexao") is not None:
                    itens.append((peer_id, peer["conexao"]))
            return itens

    def estado_keepalive(self, peer_id):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None:
                return None
            return {
                "conexao": peer.get("conexao"),
                "status": peer.get("status"),
                "ultimo_ping_envio": peer.get("ultimo_ping_envio"),
                "ping_pendente": peer.get("ping_pendente"),
                "falhas_ping": peer.get("falhas_ping", 0),
            }

    def registrar_falha_ping(self, peer_id, conexao):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None or peer.get("conexao") is not conexao or peer.get("status") != Estado.CONNECTED:
                return None
            peer["falhas_ping"] = peer.get("falhas_ping", 0) + 1
            peer["ping_pendente"] = None
            peer["ultimo_ping_envio"] = None
            return peer["falhas_ping"]

# funcao que verifica o erro de conxao de um peer e calcula backoff
    def registra_erro(self, peer_id):
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer is None or peer["conexao"] is not None:
                return
            peer["tentativas"] += 1
            if peer["tentativas"] >= self.max_tentativas:
                peer["status"] = Estado.GONE
                peer["proxima_tentativa"] = None
                logger.info("Peer %s marcado como GONE após %d tentativas", peer_id, peer["tentativas"])
                return
            espera = min(self.max_backoff, self.base_backoff * 2 ** (peer["tentativas"] - 1))
            peer["proxima_tentativa"] = time.time() + espera
            peer["status"] = Estado.STALE
            logger.warning(
                "Falha de conexão com %s (tentativa %d/%d); próximo retry em %.1fs",
                peer_id,
                peer["tentativas"],
                self.max_tentativas,
                espera,
            )

        
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
                logger.info("Conexão duplicada com %s: mantendo conexão existente (%s)", peer_id, peer.get("direcao"))
                return False, conexao

            agora = time.time()
            peer["conexao"] = conexao
            peer["direcao"] = direcao
            peer["tem_hangman"] = tem_hangman
            peer["status"] = Estado.CONNECTED
            peer["tentativas"] = 0
            peer["proxima_tentativa"] = None
            peer["ultimo_contato"] = agora
            peer["ultimo_ping_envio"] = None
            peer["ping_pendente"] = None
            peer["falhas_ping"] = 0
            if antiga is not None:
                logger.info("Conexão com %s substituída pela direção %s", peer_id, direcao)
            else:
                logger.info("Peer %s conectado (%s)", peer_id, direcao)
            return True, antiga