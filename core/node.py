"""El nodo: proceso de forwarding y pegamento entre transporte y routing.

El enunciado pide que cada nodo corra dos servicios en paralelo:

    Forwarding -> esta clase. Maneja los paquetes entrantes (entregar,
                  reenviar o pasar al routing) y los salientes.
    Routing    -> la instancia de `RoutingAlgorithm`, que corre sus propias
                  tareas asincronas (anuncios de vector, LSPs, recalculos).

Ambos conviven sobre el mismo bucle de asyncio: el servidor del transporte,
el sondeo de vecinos, las tareas del algoritmo y la consola interactiva son
tareas concurrentes independientes.
"""

import asyncio

from core import packet as pk
from core.neighbors import NeighborTable


class Node:
    def __init__(self, config, algorithm_factory, transport_factory, log):
        self.config = config
        self.log = log
        self.address = config.address
        self.label = config.label

        self.neighbors = NeighborTable(self, on_change=self._on_neighbor_change)
        self.algorithm = algorithm_factory(self)
        self.transport = transport_factory(self)

        self.stats = {"recibidos": 0, "entregados": 0, "reenviados": 0, "descartados": 0}

    @property
    def proto(self):
        return self.algorithm.proto

    def label_of(self, address):
        return self.config.label_of(address)

    # ------------------------------------------------------------ ciclo de vida

    async def start(self):
        await self.transport.start()
        self.neighbors.load(self.config.my_neighbors())
        self.log.info(
            "nodo %s (%s) | algoritmo=%s | vecinos configurados: %s",
            self.label, self.address, self.proto,
            ", ".join(n.label for n in self.neighbors.all()) or "(ninguno)",
        )
        await self.neighbors.start()
        await self.algorithm.start()

    async def stop(self):
        await self.algorithm.stop()
        await self.neighbors.stop()
        await self.transport.stop()

    async def _on_neighbor_change(self, event, neighbor):
        await self.algorithm.on_neighbor_change(event, neighbor)

    # ------------------------------------------------------------------- salida

    async def send_direct(self, address, pkt):
        """Envia un paquete a un vecino directo por el transporte.

        Marca el paquete con la cabecera `via` para que el receptor sepa por
        que enlace le llego; es lo que permite el split horizon en DVR y el
        no reenviar por donde llego en Flooding.
        """
        pk.set_header(pkt, "via", self.address)
        return await self.transport.send(address, pkt)

    async def send_message(self, destination, text, ttl=pk.DEFAULT_TTL):
        """Origina un mensaje de usuario hacia `destination`."""
        if destination == self.address:
            self._deliver(pk.make_packet(self.proto, pk.TYPE_MESSAGE,
                                         self.address, self.address, text, ttl))
            return True

        pkt = pk.make_packet(
            proto=self.proto,
            ptype=pk.TYPE_MESSAGE,
            frm=self.address,
            to=destination,
            payload=text,
            ttl=ttl,
            headers=[{"mid": pk.new_id()}, {"hops": 0}, {"path": self.label}],
        )

        self.algorithm.is_duplicate(pkt)   # registra el mid propio
        targets = self.algorithm.route(pkt)
        if not targets:
            self.log.error("sin ruta hacia %s: el paquete no se envio",
                           self.label_of(destination))
            return False

        for address in targets:
            await self.send_direct(address, pkt)
        self.log.info("mensaje enviado a %s via %s", self.label_of(destination),
                      ", ".join(self.label_of(a) for a in targets))
        return True

    # ------------------------------------------------------- entrada (forwarding)

    async def on_packet(self, pkt):
        """Punto de entrada de todo paquete que llega por el transporte."""
        if not pk.is_valid(pkt):
            self.stats["descartados"] += 1
            self.log.debug("paquete invalido descartado")
            return

        self.stats["recibidos"] += 1
        via = pk.get_header(pkt, "via")
        ptype = pkt.get("type")

        if ptype == pk.TYPE_HELLO:
            await self.neighbors.handle_hello(pkt)
        elif ptype == pk.TYPE_ECHO:
            await self.neighbors.handle_echo(pkt)
        elif ptype == pk.TYPE_INFO:
            await self.algorithm.handle_info(pkt)
        elif ptype == pk.TYPE_MESSAGE:
            await self._handle_data(pkt, via)
        else:
            self.log.debug("tipo de paquete desconocido: %s", ptype)

    async def _handle_data(self, pkt, via):
        if self.algorithm.is_duplicate(pkt, via):
            self.stats["descartados"] += 1
            return

        if pkt.get("to") == self.address:
            self._deliver(pkt)
            return

        ttl = int(pkt.get("ttl", 0)) - 1
        if ttl <= 0:
            self.stats["descartados"] += 1
            self.log.warning("TTL agotado, se descarta: %s", pk.summary(pkt))
            return
        pkt["ttl"] = ttl

        hops = pk.get_header(pkt, "hops")
        pk.set_header(pkt, "hops", (hops or 0) + 1)
        camino = pk.get_header(pkt, "path")
        pk.set_header(pkt, "path", "{},{}".format(camino, self.label) if camino else self.label)

        targets = self.algorithm.route(pkt, via)
        if not targets:
            self.stats["descartados"] += 1
            self.log.warning("sin ruta hacia %s, se descarta el paquete",
                             self.label_of(pkt.get("to")))
            return

        self.stats["reenviados"] += 1
        for address in targets:
            await self.send_direct(address, pkt)
        self.log.info("reenviado %s -> %s (%s)",
                      self.label_of(pkt.get("from")), self.label_of(pkt.get("to")),
                      ", ".join(self.label_of(a) for a in targets))

    def _deliver(self, pkt):
        """El paquete es para este nodo: se entrega al usuario."""
        self.stats["entregados"] += 1
        camino = pk.get_header(pkt, "path")
        recorrido = "{},{}".format(camino, self.label) if camino else self.label
        saltos = recorrido.count(",")
        print(
            "\n=== MENSAJE RECIBIDO ===\n"
            "  de     : {}\n"
            "  saltos : {}\n"
            "  ruta   : {}\n"
            "  texto  : {}\n".format(
                self.label_of(pkt.get("from")), saltos, recorrido, pkt.get("payload")
            ),
            flush=True,
        )
