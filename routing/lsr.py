import asyncio
import time

from core import packet as pk
from routing.common.base import RoutingAlgorithm
from routing.common.shortest_path import path_to, shortest_paths
from routing.flooding import Flooding

LSP_INTERVAL = 8.0
LSP_LIFETIME = LSP_INTERVAL * 3
BROADCAST = "*"


class LinkStateRouting(RoutingAlgorithm):
    proto = pk.PROTO_LSR

    def __init__(self, node):
        super().__init__(node)
        # base de datos de estado de enlace
        self.lsdb = {}
        # numero de secuencia de mis propios LSP
        self.seq = 0
        # resultado de Dijkstra sobre la LSDB
        self.dist = {}
        self.next_hop = {}
        self.previous = {}
        # la difusion de los LSP se delega en Flooding, no se reimplementa
        self.flooder = Flooding(node)
        self._lock = asyncio.Lock()
        self._task = None

    async def start(self):
        await self._originate()
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        while True:
            await asyncio.sleep(LSP_INTERVAL)
            async with self._lock:
                if self._expire_stale():
                    self._recompute()
            await self._originate()

    async def on_neighbor_change(self, event, neighbor):
        await self._originate()

    async def handle_info(self, pkt):
        lsp = self._parse_lsp(pkt)
        if lsp is None:
            return
        origin, seq, links = lsp

        if origin == self.node.address:
            # mi propio LSP reflejado por la red, adelantar el contador si vuelve con una secuencia mayor
            async with self._lock:
                if seq > self.seq:
                    self.seq = seq
            return

        via = pk.get_header(pkt, "via")
        if self.flooder.is_duplicate(pkt, via):
            return

        async with self._lock:
            known = self.lsdb.get(origin)
            # un LSP viejo o repetido no se guarda ni se reinunda: asi termina la inundacion
            if known is not None and seq <= known["seq"]:
                return
            self.lsdb[origin] = {"seq": seq, "links": links, "ts": time.monotonic()}
            self._recompute()

        await self._reflood(pkt, via)

    def route(self, pkt, via=None):
        destination = pkt.get("to")
        hop = self.next_hop.get(destination)
        if hop is not None:
            return [hop]
        # respaldo mientras la LSDB converge, si el destino es un vecino vivo, entregarselo
        if destination in self.node.neighbors.alive_addresses():
            return [destination]
        return []

    def table_rows(self):
        label = self.node.label_of
        rows = [
            (label(dest), label(hop), self.dist.get(dest, float("inf")))
            for dest, hop in self.next_hop.items()
        ]
        return sorted(rows, key=lambda r: r[0])

    def describe(self):
        label = self.node.label_of
        now = time.monotonic()
        lines = ["LSDB ({} nodos):".format(len(self.lsdb))]
        for origin in sorted(self.lsdb, key=label):
            entry = self.lsdb[origin]
            enlaces = ", ".join(
                "{}={:.1f}".format(label(a), c) for a, c in sorted(entry["links"].items())
            ) or "(sin enlaces)"
            lines.append("  {} seq={} edad={:.0f}s enlaces: {}".format(
                label(origin), entry["seq"], now - entry["ts"], enlaces))

        lines.append("rutas completas:")
        for dest in sorted(self.next_hop, key=label):
            ruta = path_to(self.previous, self.node.address, dest)
            lines.append("  {} : {}".format(label(dest), " -> ".join(label(n) for n in ruta)))
        return "\n".join(lines)

    def _parse_lsp(self, pkt):
        # valida el paquete y devuelve origen, secuencia, enlaces o None
        payload = pkt.get("payload")
        if not isinstance(payload, dict) or payload.get("kind") != "lsp":
            self.log.debug("paquete info sin LSP valido, se descarta")
            return None

        origin = payload.get("origin") or pkt.get("from")
        raw_links = payload.get("links")
        if not isinstance(origin, str) or not isinstance(raw_links, dict):
            return None

        try:
            seq = int(payload.get("seq"))
        except (TypeError, ValueError):
            return None

        links = {}
        for address, cost in raw_links.items():
            try:
                links[str(address)] = float(cost)
            except (TypeError, ValueError):
                continue
        return origin, seq, links

    async def _originate(self):
        # emite un LSP propio con el estado actual de mis enlaces
        async with self._lock:
            self.seq += 1
            links = {
                address: float(cost)
                for address, cost in self.node.neighbors.alive_costs().items()
            }
            self.lsdb[self.node.address] = {
                "seq": self.seq, "links": links, "ts": time.monotonic(),
            }
            self._recompute()
            pkt = self._make_lsp(self.seq, links)

        # se registra el mid propio para descartar el LSP cuando la red lo refleje
        self.flooder.is_duplicate(pkt)
        await self._flood(pkt, None)

    def _make_lsp(self, seq, links):
        return pk.make_packet(
            proto=self.proto,
            ptype=pk.TYPE_INFO,
            frm=self.node.address,
            to=BROADCAST,
            payload={
                "kind": "lsp",
                "origin": self.node.address,
                "seq": seq,
                "links": links,
            },
            ttl=pk.DEFAULT_TTL,
            headers=[{"mid": pk.new_id()}],
        )

    async def _flood(self, pkt, via):
        for address in self.flooder.route(pkt, via):
            await self.node.send_direct(address, pkt)

    async def _reflood(self, pkt, via):
        # reenvia un LSP ajeno a los demas vecinos, gastando un salto de TTL
        ttl = int(pkt.get("ttl", 0)) - 1
        if ttl <= 0:
            return
        forward = dict(pkt)
        forward["ttl"] = ttl
        forward["headers"] = [dict(h) for h in pkt.get("headers") or [] if isinstance(h, dict)]
        await self._flood(forward, via)

    def _expire_stale(self):
        # descarta los LSP que dejaron de refrescarse
        now = time.monotonic()
        vencidos = [
            origin for origin, entry in self.lsdb.items()
            if origin != self.node.address and now - entry["ts"] > LSP_LIFETIME
        ]
        for origin in vencidos:
            self.log.warning("LSP de %s expirado, se saca de la LSDB",
                             self.node.label_of(origin))
            del self.lsdb[origin]
        return bool(vencidos)

    def _build_graph(self):
        # reconstruye la topologia a partir de la LSDB
        graph = {}
        for origin, entry in self.lsdb.items():
            links = {}
            for address, cost in entry["links"].items():
                other = self.lsdb.get(address)
                # un enlace a medio converger produce agujeros negros, solo se usa si el otro extremo tambien lo declara o si aun no se conoce su LSP
                if other is not None and origin not in other["links"]:
                    continue
                links[address] = cost
            graph[origin] = links
        return graph

    def _recompute(self):
        anterior = (self.dist, self.next_hop)
        self.dist, self.next_hop, self.previous = shortest_paths(
            self._build_graph(), self.node.address)
        # se registra solo cuando la tabla cambia de verdad, para no llenar el log
        if anterior != (self.dist, self.next_hop):
            self.log.info("tabla LSR recalculada: %d destinos (LSDB con %d nodos)",
                          len(self.next_hop), len(self.lsdb))