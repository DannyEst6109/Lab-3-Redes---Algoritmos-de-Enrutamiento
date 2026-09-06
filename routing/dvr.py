"""Distance Vector Routing.

Responsable: Renato

Bellman-Ford distribuido. Ningun nodo ve el mapa completo de la red: cada uno
conoce el costo hacia sus vecinos directos (via HELLO/ECHO, en
`self.node.neighbors.alive_costs()`) y el vector de distancias que esos
vecinos le anuncian. Con eso calcula:

    D(x, y) = min sobre v vecino de [ c(x, v) + D(v, y) ]

y publica su propio vector a los vecinos. La informacion se propaga de
vecino en vecino hasta que la red converge.


FORMATO DEL PAQUETE DE ANUNCIO (elegido para este grupo, Kevin dijo que cada uno elegía jaja)
Se usa:

    tipo    : "info"
    ttl     : 1              (solo va al vecino directo, DVR no inunda)
    payload : {
        "kind": "dv",
        "vector": {
            "direccion_destino": {"cost": <float>, "hops": <int>},
            ...
        },
    }

Se anuncia `hops` junto al costo porque el costo es un RTT en milisegundos,
no un conteo de saltos: poner un limite sobre el costo declararia
inalcanzables rutas normales (un enlace ya cuesta 10-20ms). El limite de
saltos (MAX_HOPS) se aplica sobre `hops`, y el costo usa un centinela de
infinito (INFINITY) porque JSON no tiene infinito real.

El nodo siempre se anuncia a si mismo con costo 0 y 0 saltos, para que el
resto de la red aprenda como llegar hasta el sin depender de que alguien mas
lo redistribuya primero.


PROBLEMAS CLASICOS 
1. COUNT TO INFINITY -> dos defensas:
   - SPLIT HORIZON CON POISON REVERSE (`_vector_for`): al vecino que es mi
     siguiente salto hacia un destino le anuncio ese destino con costo
     INFINITY, para que nunca intente usarme a mi como respaldo suyo.
   - LIMITE DE SALTOS (`MAX_HOPS`, estilo RIP=16): una ruta que superaria ese
     numero de saltos se descarta al recalcular (`_recompute`).

2. RUTAS ZOMBI -> cada vector recibido se guarda con marca de tiempo
   (`self.received[origen]["timestamp"]`) y `_expire_stale()`, llamado en
   cada ciclo del anuncio periodico, descarta los vectores que no se han
   refrescado en `STALE_AFTER` segundos (vecino caido que dejo de anunciar).
   Ademas, `on_neighbor_change("down", ...)` borra el vector de inmediato en
   cuanto HELLO/ECHO detecta la caida, sin esperar a que expire por tiempo.

3. VALIDAR EL ORIGEN -> `handle_info()` descarta cualquier paquete cuyo
   `from` no sea un vecino directo (`self.node.neighbors.is_neighbor(...)`).

4. TRIGGERED UPDATES -> ademas del anuncio periodico (`_loop`), se reanuncia
   de inmediato cuando la tabla cambia por: un vector nuevo (`handle_info`),
   un vecino que sube/cae/cambia de costo (`on_neighbor_change`). Al vecino
   que acaba de subir tambien se le manda el vector actual sin esperar el
   siguiente ciclo, para acelerar la convergencia.

5. CONCURRENCIA -> `handle_info()`, el ciclo periodico y
   `on_neighbor_change()` pueden disparar un recalculo al mismo tiempo.
   Un `asyncio.Lock` protege la seccion que lee/escribe `self.table` y
   `self.received`.


PROBARLO
Prueba end-to-end:

       python scripts/test_network.py --algo dvr --topo configs/topo-weighted.txt

   Con esa topologia, la tabla del nodo A debe converger a costo 10 hacia G
   por la ruta A-B-C-E-G, igual que Dijkstra centralizado: si no coincide,
   hay un error.

Prueba para casos específicos de este algoritmo:
        python scripts/test_dvr.py  
"""

import asyncio
import time

from core import packet as pk
from routing.common.base import RoutingAlgorithm

INFINITY = 1e9          # simula infinito
MAX_HOPS = 16            # limite de saltos, estilo RIP
ANNOUNCE_INTERVAL = 5.0  # segundos entre anuncios periodicos del vector
STALE_AFTER = ANNOUNCE_INTERVAL * 3  # vector sin refrescar -> se descarta


class DistanceVector(RoutingAlgorithm):
    proto = pk.PROTO_DVR

    def __init__(self, node):
        super().__init__(node)
        #: {destino: {"cost": costo, "next_hop": direccion, "hops": saltos}}
        self.table = {}
        #: vectores recibidos de cada vecino: {vecino: {"vector": {...}, "timestamp": t}}
        self.received = {}
        self._lock = asyncio.Lock()
        self._task = None

    # ciclo de vida

    async def start(self):
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        """Anuncio periodico: recalcula, expira vectores viejos y reanuncia."""
        while True:
            async with self._lock:
                self._expire_stale()
                self._recompute()
            await self._broadcast()
            await asyncio.sleep(ANNOUNCE_INTERVAL)

    # eventos

    async def on_neighbor_change(self, event, neighbor):
        """`event` es 'up', 'down' o 'cost'. Recalcula y reanuncia."""
        async with self._lock:
            if event == "down":
                # vector ya no es confiable: no esperar a que expire solo
                self.received.pop(neighbor.address, None)
            changed = self._recompute()

        if event == "up":
            # acelera la convergencia: no esperar el proximo ciclo periodico
            await self._send_vector_to(neighbor.address)

        if changed or event in ("down", "cost"):
            await self._broadcast()

    async def handle_info(self, pkt):
        """Recibe el vector de un vecino, lo guarda y recalcula la tabla."""
        origin = pkt.get("from")
        if not self.node.neighbors.is_neighbor(origin):
            self.log.debug("vector DVR de %s ignorado: no es vecino directo",
                           self.node.label_of(origin) if origin else origin)
            return

        payload = pkt.get("payload")
        if not isinstance(payload, dict) or payload.get("kind") != "dv":
            self.log.debug("paquete info con payload DVR invalido, se descarta")
            return

        vector = payload.get("vector")
        if not isinstance(vector, dict):
            return

        cleaned = {}
        for dest, entry in vector.items():
            if not isinstance(entry, dict):
                continue
            try:
                cleaned[dest] = {
                    "cost": float(entry.get("cost", INFINITY)),
                    "hops": int(entry.get("hops", MAX_HOPS)),
                }
            except (TypeError, ValueError):
                continue

        async with self._lock:
            self.received[origin] = {"vector": cleaned, "timestamp": time.monotonic()}
            changed = self._recompute()

        if changed:
            await self._broadcast()

    # forwarding

    def route(self, pkt, via=None):
        entry = self.table.get(pkt.get("to"))
        if entry is None:
            return []
        return [entry["next_hop"]]

    # inspeccion

    def table_rows(self):
        label = self.node.label_of
        rows = [
            (label(dest), label(info["next_hop"]), info["cost"])
            for dest, info in self.table.items()
        ]
        return sorted(rows, key=lambda r: r[0])

    def describe(self):
        label = self.node.label_of
        origenes = ", ".join(label(a) for a in self.received) or "(ninguno)"
        lines = ["vectores recibidos de: {}".format(origenes)]
        for dest, info in sorted(self.table.items(), key=lambda kv: label(kv[0])):
            lines.append("  {} : costo={:.1f} saltos={} via {}".format(
                label(dest), info["cost"], info["hops"], label(info["next_hop"])))
        return "\n".join(lines)

    # internos

    def _expire_stale(self):
        """Descarta vectores de vecinos que dejaron de anunciar (rutas zombi)."""
        now = time.monotonic()
        vencidos = [addr for addr, info in self.received.items()
                    if now - info["timestamp"] > STALE_AFTER]
        for addr in vencidos:
            self.log.warning("vector DVR de %s expirado, se descarta",
                             self.node.label_of(addr))
            del self.received[addr]

    def _recompute(self):
        """Bellman-Ford local: recalcula self.table a partir de lo conocido.
        Devuelve True si la tabla cambio respecto a la anterior (para decidir
        si conviene reanunciar de inmediato, ademas del ciclo periodico).
        """
        neighbor_costs = self.node.neighbors.alive_costs()
        me = self.node.address

        destinos = set(neighbor_costs)
        for info in self.received.values():
            destinos.update(info["vector"])
        destinos.discard(me)

        new_table = {}
        for dest in destinos:
            best_cost, best_hop, best_hops = INFINITY, None, MAX_HOPS

            # opcion 1: enlace directo al destino (el destino es mi vecino)
            if dest in neighbor_costs:
                best_cost, best_hop, best_hops = neighbor_costs[dest], dest, 1

            # opcion 2: via cada vecino, usando su vector anunciado
            for n_addr, n_cost in neighbor_costs.items():
                learned = self.received.get(n_addr)
                if learned is None:
                    continue
                entry = learned["vector"].get(dest)
                if entry is None:
                    continue
                if entry["cost"] >= INFINITY or entry["hops"] >= MAX_HOPS:
                    continue  # ruta envenenada o ya en el limite: ignorar

                total_cost = n_cost + entry["cost"]
                total_hops = entry["hops"] + 1
                if total_hops > MAX_HOPS:
                    continue

                if total_cost < best_cost:
                    best_cost, best_hop, best_hops = total_cost, n_addr, total_hops

            if best_hop is not None:
                new_table[dest] = {
                    "cost": best_cost, "next_hop": best_hop, "hops": best_hops,
                }

        changed = new_table != self.table
        if changed:
            self.log.info("tabla DVR recalculada: %d destinos", len(new_table))
        self.table = new_table
        return changed

    def _vector_for(self, target_addr):
        """Vector a anunciar a `target_addr`, con split horizon + poison reverse."""
        vector = {self.node.address: {"cost": 0.0, "hops": 0}}
        for dest, info in self.table.items():
            if info["next_hop"] == target_addr:
                # a quien me da la ruta no le sirvo de respaldo: la enveneno
                vector[dest] = {"cost": INFINITY, "hops": info["hops"]}
            else:
                vector[dest] = {"cost": info["cost"], "hops": info["hops"]}
        return vector

    async def _send_vector_to(self, address):
        pkt = pk.make_packet(
            proto=self.proto,
            ptype=pk.TYPE_INFO,
            frm=self.node.address,
            to=address,
            payload={"kind": "dv", "vector": self._vector_for(address)},
            ttl=1,
        )
        await self.node.send_direct(address, pkt)

    async def _broadcast(self):
        for address in self.node.neighbors.alive_addresses():
            await self._send_vector_to(address)