"""Transporte sobre XMPP (fase 2: entrega oficial).

Cada nodo se autentica en el servidor XMPP con su propio JID y envia los
paquetes como el cuerpo (JSON serializado) de un stanza <message> dirigido al
JID del vecino. La logica de enrutamiento es exactamente la misma que en la
fase 1: lo unico que cambia es el medio.

Requiere `slixmpp` (ver requirements.txt). El import es perezoso para que el
proyecto se pueda ejecutar en modo sockets sin instalar la dependencia.
"""

import asyncio

from core import packet as pk
from transport.base import Transport


class XMPPTransport(Transport):
    def __init__(self, node, jid=None, password=None, server=None, port=5222):
        super().__init__(node)
        self.jid = jid or node.address
        self.password = password
        self.server = server
        self.port = port
        self._client = None
        self._ready = asyncio.Event()

    async def start(self):
        try:
            from slixmpp import ClientXMPP
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise RuntimeError(
                "el transporte XMPP requiere slixmpp: pip install -r requirements.txt"
            ) from exc

        node = self.node
        ready = self._ready

        class _Client(ClientXMPP):
            def __init__(self, jid, password):
                super().__init__(jid, password)
                self.add_event_handler("session_start", self._on_start)
                self.add_event_handler("message", self._on_message)

            async def _on_start(self, _event):
                self.send_presence()
                await self.get_roster()
                node.log.info("sesion XMPP iniciada como %s", self.boundjid.full)
                ready.set()

            async def _on_message(self, msg):
                if msg["type"] not in ("chat", "normal"):
                    return
                try:
                    parsed = pk.decode(msg["body"])
                except (ValueError, TypeError) as exc:
                    node.log.debug("stanza con cuerpo no JSON descartado: %s", exc)
                    return
                await node.on_packet(parsed)

        self._client = _Client(self.jid, self.password)
        self._client.register_plugin("xep_0030")  # Service Discovery
        self._client.register_plugin("xep_0199")  # XMPP Ping

        if self.server:
            self._client.connect((self.server, self.port))
        else:
            self._client.connect()

        await asyncio.wait_for(self._ready.wait(), timeout=30.0)

    async def stop(self):
        if self._client is not None:
            self._client.disconnect()
            self._client = None

    async def send(self, address, pkt):
        if self._client is None:
            return False
        try:
            self._client.send_message(mto=address, mbody=pk.encode(pkt).decode("utf-8").strip(),
                                      mtype="chat")
            return True
        except Exception as exc:  # pragma: no cover - errores de red del servidor
            self.node.log.debug("no se pudo entregar a %s via XMPP: %s", address, exc)
            return False
