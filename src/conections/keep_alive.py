import threading
import time

from conections.protocolo import montar, agora_iso

def _enviar_pint(canal):
    msg = montar("PING", timestamp=agora_iso())
    canal.pings[msg["msg_id"]] = time.perf_counter()
    canal.enviar(msg)