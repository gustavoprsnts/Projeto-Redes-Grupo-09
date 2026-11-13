import threading


class PeerTable:
    def __init__(self):
        self.peers = {}
        self.lock = threading.Lock()


        def adicionar(self,dados):
            with self.Lock:
                self.peers[peer_id] = dados

        def remove(self, dados):
            with self.Lock:
               self.peers.pop(peer_id,None)
        
        def listar(self,dados):
            with self.Lock:
                self.peers.list(self.peers.values())

    