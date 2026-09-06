"""Formato de paquete de la red.

Estructura JSON definida en el enunciado del laboratorio:

    {
      "proto"  : "dijkstra|flooding|lsr|dvr",
      "type"   : "message|echo|info|hello",
      "from"   : "foo@bar.com/123",
      "to"     : "yolo@bar.com/777",
      "ttl"    : 5,
      "headers": [{"clave": "valor"}, ...],
      "payload": <contenido segun el tipo>
    }

`headers` es una lista de diccionarios de un solo par para mantener
compatibilidad con el formato acordado entre grupos; las funciones
`get_header`/`set_header` la tratan como si fuera un mapa.
"""

import json
import uuid

# Protocolos (algoritmo de enrutamiento con el que se levanto la red).
PROTO_DIJKSTRA = "dijkstra"
PROTO_FLOODING = "flooding"
PROTO_LSR = "lsr"
PROTO_DVR = "dvr"

# Tipos de paquete.
TYPE_MESSAGE = "message"   # datos de usuario
TYPE_HELLO = "hello"       # sondeo de vecino
TYPE_ECHO = "echo"         # respuesta al sondeo (permite medir el RTT)
TYPE_INFO = "info"         # vectores de distancia, LSPs, tablas

DEFAULT_TTL = 16


def new_id() -> str:
    """Identificador corto y unico para deduplicar paquetes inundados."""
    return uuid.uuid4().hex[:12]


def make_packet(proto, ptype, frm, to, payload="", ttl=DEFAULT_TTL, headers=None):
    return {
        "proto": proto,
        "type": ptype,
        "from": frm,
        "to": to,
        "ttl": ttl,
        "headers": list(headers) if headers else [],
        "payload": payload,
    }


def get_header(pkt, key, default=None):
    for entry in pkt.get("headers") or []:
        if isinstance(entry, dict) and key in entry:
            return entry[key]
    return default


def set_header(pkt, key, value):
    headers = pkt.setdefault("headers", [])
    for entry in headers:
        if isinstance(entry, dict) and key in entry:
            entry[key] = value
            return pkt
    headers.append({key: value})
    return pkt


def encode(pkt) -> bytes:
    """Serializa un paquete como una linea JSON (delimitador \n)."""
    return (json.dumps(pkt, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def decode(raw) -> dict:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    pkt = json.loads(raw)
    if not isinstance(pkt, dict):
        raise ValueError("el paquete no es un objeto JSON")
    return pkt


def is_valid(pkt) -> bool:
    """Validacion minima: los campos obligatorios del protocolo."""
    return (
        isinstance(pkt, dict)
        and isinstance(pkt.get("proto"), str)
        and isinstance(pkt.get("type"), str)
        and isinstance(pkt.get("from"), str)
        and isinstance(pkt.get("ttl"), int)
    )


def summary(pkt) -> str:
    """Representacion compacta para los logs."""
    return "{}/{} {} -> {} ttl={}".format(
        pkt.get("proto"), pkt.get("type"), pkt.get("from"), pkt.get("to"), pkt.get("ttl")
    )
