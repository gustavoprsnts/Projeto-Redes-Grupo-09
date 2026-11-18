"""Constantes e utilitarios do protocolo Peer-Peer (JSON em uma linha, UTF-8)."""
import json
import uuid
from datetime import datetime, timezone

MAX_LINHA = 32768
VERSAO = "1.0"
FEATURES = ["hangman"]

# mensagens de conexao: omitem src/dst
SEM_ENDERECO = frozenset({"HELLO", "HELLO_OK", "PING", "PONG"})
# os exemplos da especificacao omitem src/dst nestas; ao receber, tolera-se a ausencia
ENDERECO_OPCIONAL = frozenset({"GAME_LIST", "GAME_LIST_OK"})

# campos obrigatorios por tipo de mensagem
OBRIGATORIOS = {
    "HELLO": ["peer_id", "version", "features"],
    "HELLO_OK": ["peer_id", "version", "features"],
    "PING": ["timestamp"],
    "PONG": ["timestamp"],
    "BYE": [],
    "BYE_OK": [],
    "ERROR": ["code"],
    "GAME_LIST": [],
    "GAME_LIST_OK": ["games"],
    "JOIN": ["game_id"],
    "JOIN_OK": ["game_id", "players", "rejoin"],
    "JOIN_ERR": ["game_id", "reason"],
    "LEAVE": ["game_id"],
    "LEAVE_OK": ["game_id"],
    "GAME_START": ["game_id", "players", "lives", "word_length", "word_hash", "turn_timeout"],
    "STATE": ["game_id", "seq", "masked", "wrong_letters", "lives", "turn", "players"],
    "GUESS": ["game_id"],
    "GUESS_RESULT": ["game_id", "accepted"],
    "GAME_OVER": ["game_id", "result"],
}

# tipos que so fazem sentido entre peers que anunciaram a feature "hangman"
TIPOS_JOGO = frozenset(
    t for t in OBRIGATORIOS if t.startswith(("GAME_", "JOIN", "LEAVE", "GUESS", "STATE")))

_TIPOS_CAMPOS = {
    "peer_id": str, "version": str, "features": list, "timestamp": str, "code": str,
    "games": list, "game_id": str, "players": list, "rejoin": bool, "reason": str,
    "lives": int, "word_length": int, "word_hash": str, "turn_timeout": (int, float),
    "seq": int, "masked": str, "wrong_letters": list, "turn": str, "accepted": bool,
    "result": str,
}


def agora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def novo_id() -> str:
    return str(uuid.uuid4())


def montar(tipo: str, src=None, dst=None, msg_id=None, **campos) -> dict:
    """Monta uma mensagem com o envelope padrao (ttl = 1)."""
    msg = {"type": tipo, "msg_id": msg_id or novo_id()}
    if src is not None:
        msg["src"] = src
    if dst is not None:
        msg["dst"] = dst
    if tipo not in ("HELLO", "HELLO_OK"):
        campos.setdefault("timestamp", agora_iso())
    msg.update(campos)
    msg["ttl"] = 1
    return msg


def codificar(msg: dict) -> bytes:
    return (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def validar(msg: dict):
    """Devolve None se a mensagem e valida, ou a descricao do problema."""
    if not isinstance(msg.get("type"), str):
        return "campo 'type' ausente"
    if not isinstance(msg.get("msg_id"), str):
        return "campo 'msg_id' ausente"
    for campo in OBRIGATORIOS.get(msg["type"], []):
        if campo not in msg:
            return f"campo '{campo}' ausente"
    for campo in ("src", "dst"):
        if campo in msg and not isinstance(msg[campo], str):
            return f"tipo invalido em '{campo}'"
    if msg["type"] not in SEM_ENDERECO and msg["type"] not in ENDERECO_OPCIONAL:
        for campo in ("src", "dst"):
            if campo not in msg:
                return f"campo '{campo}' ausente"
    for campo, tipo in _TIPOS_CAMPOS.items():
        if campo in msg and not isinstance(msg[campo], tipo):
            return f"tipo invalido em '{campo}'"
    

    if msg.get("ttl") != 1:
        return "ttl inválido"

    if msg["type"] == "GUESS":
        tem_letra = "letter" in msg
        tem_palavra = "word" in msg
        if tem_letra == tem_palavra:
            return "GUESS exige letter ou word"
        if tem_letra and not isinstance(msg.get("letter"), str):
            return "letter deve ser string"
        if tem_palavra and not isinstance(msg.get("word"), str):
            return "word deve ser string"

        return None

def criar_envelope(
    tipo: str,
    src: str | None = None,
    dst: str | None = None,
    msg_id: str | None = None,
    **campos: object,
) -> dict[str, object]:
    mensagem: dict[str, object] = {
        "type": tipo,
        "msg_id": msg_id or str(uuid.uuid4()),
        "ttl": 1,
    }

    if src is not None:
        mensagem["src"] = src

    if dst is not None:
        mensagem["dst"] = dst

    mensagem.update(campos)
    return mensagem
