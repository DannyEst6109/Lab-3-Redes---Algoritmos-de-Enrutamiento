"""Dijkstra puro (modo de red estatico).

Es el unico algoritmo al que el enunciado le concede la topologia completa
como entrada. Calcula la tabla de enrutamiento una sola vez, al arrancar,
resolviendo los caminos minimos desde este nodo.

Es estatico por definicion: si la topologia real cambia, la tabla queda
desactualizada porque no hay intercambio de informacion entre nodos. Lo unico
que este nodo puede observar por si mismo es el estado de *sus propios*
enlaces (via HELLO/ECHO), asi que ante la caida de un vecino directo recalcula
excluyendo ese enlace. No puede hacer mas: la caida de un enlace remoto le es
invisible, y esa limitacion es precisamente lo que motivan LSR y DVR.
"""

from core import packet as pk
from routing.base import RoutingAlgorithm
from routing.dijkstra_core import path_to, shortest_paths


class Dijkstra(RoutingAlgorithm):
    proto = pk.PROTO_DIJKSTRA

    def __init__(self, node):
        super().__init__(node)
        self.graph = node.config.full_topology()   # permitido solo en este modo
        self.dist = {}
        self.next_hop = {}
        self.previous = {}

    async def start(self):
        self._recompute()

    async def on_neighbor_change(self, event, neighbor):
        # Solo se reacciona al estado de los enlaces propios (lo unico que
        # este nodo puede medir); la topologia remota se asume fija.
        if event in ("up", "down"):
            self._recompute()

    def _recompute(self):
        graph = {node: dict(links) for node, links in self.graph.items()}

        me = self.node.address
        for neighbor in self.node.neighbors.all():
            if not neighbor.alive:
                graph.get(me, {}).pop(neighbor.address, None)
                graph.get(neighbor.address, {}).pop(me, None)

        self.dist, self.next_hop, self.previous = shortest_paths(graph, me)
        self.log.info("tabla de Dijkstra recalculada: %d destinos", len(self.next_hop))

    def route(self, pkt, via=None):
        hop = self.next_hop.get(pkt.get("to"))
        if hop is None:
            return []
        return [hop]

    def table_rows(self):
        label = self.node.label_of
        rows = [
            (label(dest), label(hop), self.dist.get(dest, float("inf")))
            for dest, hop in self.next_hop.items()
        ]
        return sorted(rows, key=lambda r: r[0])

    def describe(self):
        label = self.node.label_of
        lines = ["rutas completas:"]
        for dest in sorted(self.next_hop, key=label):
            ruta = path_to(self.previous, self.node.address, dest)
            lines.append("  {} : {}".format(label(dest), " -> ".join(label(n) for n in ruta)))
        return "\n".join(lines)
