from uuid import uuid4


def criar_envelope(
    tipo: str,
    src: str | None = None,
    dst: str | None = None,
    msg_id: str | None = None,
    **campos: object,
) -> dict[str, object]:
    mensagem: dict[str, object] = {
        "type": tipo,
        "msg_id": msg_id or str(uuid4()),
        "ttl": 1,
    }

    if src is not None:
        mensagem["src"] = src

    if dst is not None:
        mensagem["dst"] = dst

    mensagem.update(campos)
    return mensagem
