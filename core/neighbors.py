"""Descubrimiento de vecinos y medicion de costo de enlace (HELLO / ECHO).

Cada nodo conoce por configuracion la *lista* de sus vecinos, pero no sabe si
estan levantados ni que tan lejos estan. Este modulo se encarga de eso:

  - envia periodicamente un paquete HELLO a cada vecino configurado,
  - el vecino responde con un ECHO copiando la marca de tiempo original,
  - al recibir el ECHO se calcula el RTT y se suaviza con un promedio movil
    exponencial (EWMA) para obtener el costo del enlace,
  - si un vecino deja de responder durante `dead_after` segundos se marca
    como caido y se notifica al algoritmo de enrutamiento.

Es el unico componente que produce eventos de "enlace arriba/abajo", que es
lo que dispara la reconvergencia en DVR y LSR.
"""

import asyncio
import time

from core import packet as pk

HELLO_INTERVAL = 4.0     # segundos entre sondeos
DEAD_AFTER = 13.0        # sin ECHO durante este tiempo -> vecino caido
EWMA_ALPHA = 0.3         # peso de la muestra nueva en el costo del enlace
MIN_COST = 1.0           # evita costos 0 en enlaces locales muy rapidos
COST_EPSILON = 0.5       # cambio minimo de costo que dispara reconvergencia


class Neighbor:
    def __init__(self, address, label, configured_weight=None):
        self.address = address
        self.label = label
        self.configured_weight = configured_weight
        self.cost = configured_weight if configured_weight is not None else MIN_COST
        self.rtt = None
        self.alive = False
        self.last_seen = 0.0

    def __repr__(self):
        estado = "up" if self.alive else "down"
        return "<Neighbor {} {} cost={:.1f}>".format(self.label, estado, self.cost)


class NeighborTable:
    """Mantiene el estado de los vecinos directos del nodo."""

    def __init__(self, node, on_change=None):
        self.node = node
        self.on_change = on_change
        self._neighbors = {}
        self._tasks = []

    # ------------------------------------------------------------------ init

    def load(self, entries):
        """entries: [(direccion, peso_configurado_o_None)] del archivo de topologia."""
        for address, weight in entries:
            self._neighbors[address] = Neighbor(address, self.node.label_of(address), weight)

    # --------------------------------------------------------------- consulta

    def all(self):
        return list(self._neighbors.values())

    def get(self, address):
        return self._neighbors.get(address)

    def is_neighbor(self, address):
        return address in self._neighbors

    def alive_addresses(self):
        return [n.address for n in self._neighbors.values() if n.alive]

    def alive_costs(self):
        """{direccion: costo} de los enlaces actualmente operativos."""
        return {n.address: n.cost for n in self._neighbors.values() if n.alive}

    # ------------------------------------------------------------------ ciclo

    async def start(self):
        self._tasks.append(asyncio.create_task(self._hello_loop()))
        self._tasks.append(asyncio.create_task(self._monitor_loop()))

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    async def _hello_loop(self):
        while True:
            for neighbor in list(self._neighbors.values()):
                await self._send_hello(neighbor)
            await asyncio.sleep(HELLO_INTERVAL)

    async def _monitor_loop(self):
        while True:
            await asyncio.sleep(HELLO_INTERVAL / 2.0)
            now = time.monotonic()
            for neighbor in list(self._neighbors.values()):
                if neighbor.alive and (now - neighbor.last_seen) > DEAD_AFTER:
                    neighbor.alive = False
                    self.node.log.warning("vecino %s CAIDO (sin respuesta)", neighbor.label)
                    await self._notify("down", neighbor)

    async def _send_hello(self, neighbor):
        pkt = pk.make_packet(
            proto=self.node.proto,
            ptype=pk.TYPE_HELLO,
            frm=self.node.address,
            to=neighbor.address,
            payload="",
            ttl=1,
            headers=[{"t0": time.monotonic()}],
        )
        await self.node.send_direct(neighbor.address, pkt)

    # -------------------------------------------------------------- recepcion

    async def handle_hello(self, pkt):
        """Responde un sondeo devolviendo la marca de tiempo original."""
        origin = pkt.get("from")
        echo = pk.make_packet(
            proto=self.node.proto,
            ptype=pk.TYPE_ECHO,
            frm=self.node.address,
            to=origin,
            payload="",
            ttl=1,
            headers=[{"t0": pk.get_header(pkt, "t0")}],
        )
        await self.node.send_direct(origin, echo)

    async def handle_echo(self, pkt):
        """Calcula el RTT y actualiza el costo del enlace."""
        origin = pkt.get("from")
        neighbor = self._neighbors.get(origin)
        if neighbor is None:
            return

        t0 = pk.get_header(pkt, "t0")
        rtt_ms = None
        if isinstance(t0, (int, float)):
            rtt_ms = max((time.monotonic() - t0) * 1000.0, 0.0)
            neighbor.rtt = rtt_ms

        was_alive = neighbor.alive
        old_cost = neighbor.cost
        neighbor.alive = True
        neighbor.last_seen = time.monotonic()

        if neighbor.configured_weight is not None:
            neighbor.cost = neighbor.configured_weight
        elif rtt_ms is not None:
            sample = max(rtt_ms, MIN_COST)
            neighbor.cost = sample if not was_alive else (
                EWMA_ALPHA * sample + (1 - EWMA_ALPHA) * neighbor.cost
            )

        if not was_alive:
            self.node.log.info("vecino %s ACTIVO (costo %.1f)", neighbor.label, neighbor.cost)
            await self._notify("up", neighbor)
        elif abs(neighbor.cost - old_cost) > COST_EPSILON:
            await self._notify("cost", neighbor)

    async def _notify(self, event, neighbor):
        if self.on_change is not None:
            await self.on_change(event, neighbor)
