"""Pruebas del algoritmo de Distance Vector Routing.

Son deterministas y no levantan red real ni sockets: usan un `FakeNode` y una
`Red` en memoria para ejercitar `routing/dvr.py` directamente. Cubren tanto
el calculo (Bellman-Ford local) como los mecanismos propios de DVR que no
tiene Dijkstra: split horizon con poison reverse, limite de saltos,
expiracion de vectores viejos y validacion del origen.

Uso:
    python scripts/test_dvr.py
"""

import asyncio
import logging
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core import packet as pk  # noqa: E402
from routing.dvr import DistanceVector, INFINITY, MAX_HOPS, STALE_AFTER  # noqa: E402

# silenciar los logs del algoritmo (info/warning) para que la salida quede
# tan limpia como la de test_dijkstra.py
logging.disable(logging.CRITICAL)

# Misma topologia de configs/topo-weighted.txt que usa test_dijkstra.py
PESADA = {
    "A": {"B": 2, "C": 5},
    "B": {"A": 2, "C": 1, "D": 4},
    "C": {"A": 5, "B": 1, "E": 3},
    "D": {"B": 4, "E": 2, "F": 6},
    "E": {"C": 3, "D": 2, "G": 4},
    "F": {"D": 6, "G": 1},
    "G": {"E": 4, "F": 1},
}

# Respuesta conocida desde A (calculada a mano / verificada con Dijkstra en
# test_dijkstra.py): todas las rutas optimas desde A pasan por B.
ESPERADO_COSTOS = {"B": 2.0, "C": 3.0, "D": 6.0, "E": 6.0, "F": 11.0, "G": 10.0}
ESPERADO_HOPS = {"B": 1, "C": 2, "D": 2, "E": 3, "F": 5, "G": 4}

fallos = []


def verificar(descripcion, obtenido, esperado):
    if obtenido == esperado:
        print("  OK   {}".format(descripcion))
    else:
        print("  FALLO {}\n        esperado: {!r}\n        obtenido: {!r}".format(
            descripcion, esperado, obtenido))
        fallos.append(descripcion)


# infraestructura
class FakeNeighbors:
    """Sustituye a core.neighbors.NeighborTable con costos fijos controlables."""

    def __init__(self, costs):
        self._costs = dict(costs)
        self._alive = {addr: True for addr in costs}

    def is_neighbor(self, addr):
        return addr in self._costs

    def alive_costs(self):
        return {a: c for a, c in self._costs.items() if self._alive.get(a)}

    def alive_addresses(self):
        return [a for a in self._costs if self._alive.get(a)]

    def set_alive(self, addr, alive):
        self._alive[addr] = alive


class Red:
    """Red en memoria: enruta lo que un FakeNode manda con send_direct."""

    def __init__(self):
        self.nodos = {}

    def registrar(self, nodo):
        self.nodos[nodo.address] = nodo


class FakeNode:
    """Sustituye a core.node.Node: solo lo que DistanceVector necesita."""

    def __init__(self, address, red, neighbor_costs):
        self.address = address
        self.red = red
        self.log = logging.getLogger("test-dvr-" + address)
        self.neighbors = FakeNeighbors(neighbor_costs)
        self.entrante = []   # paquetes pendientes de procesar (para la simulacion)

    def label_of(self, addr):
        return addr   # en estas pruebas direccion == etiqueta

    async def send_direct(self, address, pkt):
        pk.set_header(pkt, "via", self.address)
        destino = self.red.nodos.get(address)
        if destino is not None:
            destino.entrante.append(pkt)
        # si el destino no esta registrado en esta red de prueba (pruebas
        # aisladas que no simulan la red completa), el envio simplemente se
        # descarta: no es lo que se esta probando en esos casos.


def hacer_dv(address, neighbor_costs, red=None):
    nodo = FakeNode(address, red or Red(), neighbor_costs)
    return DistanceVector(nodo), nodo


# pruebas
def prueba_seleccion_de_ruta():
    print("\n[1] recompute: elige la mejor ruta entre enlace directo y vecinos")
    dv, _ = hacer_dv("A", {"B": 2, "C": 5})
    ahora = time.monotonic()
    dv.received = {
        "B": {"vector": {"C": {"cost": 1, "hops": 1}, "D": {"cost": 4, "hops": 1}},
              "timestamp": ahora},
        "C": {"vector": {"B": {"cost": 1, "hops": 1}}, "timestamp": ahora},
    }
    dv._recompute()

    verificar("costo a B (enlace directo, nadie ofrece nada mejor)",
              round(dv.table["B"]["cost"], 1), 2.0)
    verificar("costo a C (via B: 2+1=3, mejor que el directo 5)",
              round(dv.table["C"]["cost"], 1), 3.0)
    verificar("siguiente salto a C es B, no el enlace directo", dv.table["C"]["next_hop"], "B")
    verificar("saltos a C", dv.table["C"]["hops"], 2)
    verificar("D solo es alcanzable via B (2+4=6)", round(dv.table["D"]["cost"], 1), 6.0)


def prueba_ignora_rutas_envenenadas():
    print("\n[2] una ruta entrante con costo INFINITY (poison) se ignora")
    dv, _ = hacer_dv("A", {"B": 2, "C": 5})
    ahora = time.monotonic()
    dv.received = {
        "B": {"vector": {"D": {"cost": INFINITY, "hops": 1}}, "timestamp": ahora},
        "C": {"vector": {"D": {"cost": 3, "hops": 1}}, "timestamp": ahora},
    }
    dv._recompute()
    verificar("D se alcanza por C (5+3=8), la ruta envenenada de B no compite",
              round(dv.table["D"]["cost"], 1), 8.0)
    verificar("siguiente salto a D es C", dv.table["D"]["next_hop"], "C")


def prueba_limite_de_saltos():
    print("\n[3] una ruta que supera MAX_HOPS se descarta")
    dv, _ = hacer_dv("A", {"B": 2})
    dv.received = {
        "B": {"vector": {"Z": {"cost": 1, "hops": MAX_HOPS}}, "timestamp": time.monotonic()},
    }
    dv._recompute()
    verificar("Z no aparece en la tabla: excede el limite de saltos", "Z" in dv.table, False)

    dv.received["B"]["vector"]["Z"]["hops"] = MAX_HOPS - 1
    dv._recompute()
    verificar("un salto menos si entra en la tabla", "Z" in dv.table, True)


def prueba_vector_saliente_split_horizon():
    print("\n[4] _vector_for aplica split horizon con poison reverse")
    dv, nodo = hacer_dv("A", {"B": 2, "C": 5})
    dv.table = {
        "D": {"cost": 6.0, "next_hop": "B", "hops": 2},
        "E": {"cost": 8.0, "next_hop": "C", "hops": 2},
    }
    vector_hacia_B = dv._vector_for("B")
    vector_hacia_C = dv._vector_for("C")

    verificar("a B se le envenena D (B es el siguiente salto hacia D)",
              vector_hacia_B["D"]["cost"], INFINITY)
    verificar("a B no se le envenena E (el siguiente salto es C, no B)",
              vector_hacia_B["E"]["cost"], 8.0)
    verificar("a C se le envenena E", vector_hacia_C["E"]["cost"], INFINITY)
    verificar("a C no se le envenena D", vector_hacia_C["D"]["cost"], 6.0)
    verificar("todo vector incluye la auto-anuncia con costo 0",
              vector_hacia_B[nodo.address], {"cost": 0.0, "hops": 0})


def prueba_expiracion_de_vectores():
    print("\n[5] un vector que no se refresca a tiempo se descarta (ruta zombi)")
    dv, _ = hacer_dv("A", {"B": 2, "C": 5})
    ahora = time.monotonic()
    dv.received = {
        "B": {"vector": {"D": {"cost": 4, "hops": 1}}, "timestamp": ahora - (STALE_AFTER + 5)},
        "C": {"vector": {"D": {"cost": 9, "hops": 1}}, "timestamp": ahora},
    }
    dv._expire_stale()
    verificar("el vector viejo de B se elimina", "B" in dv.received, False)
    verificar("el vector fresco de C se conserva", "C" in dv.received, True)


def prueba_handle_info_valida_origen():
    print("\n[6] handle_info descarta paquetes que no vienen de un vecino directo")

    async def cuerpo():
        dv, _ = hacer_dv("A", {"B": 2})   # C no es vecino de A
        pkt = pk.make_packet(
            proto="dvr", ptype=pk.TYPE_INFO, frm="C", to="A",
            payload={"kind": "dv", "vector": {"Z": {"cost": 1, "hops": 1}}}, ttl=1,
        )
        await dv.handle_info(pkt)
        verificar("el vector de un no-vecino se ignora por completo",
                  dv.received, {})

        pkt["from"] = "B"
        await dv.handle_info(pkt)
        verificar("el mismo vector si viene de un vecino real, se acepta",
                  "B" in dv.received, True)

    asyncio.run(cuerpo())


def prueba_route_y_table_rows():
    print("\n[7] route() y table_rows() leen la tabla ya calculada")
    dv, _ = hacer_dv("A", {"B": 2, "C": 5})
    dv.table = {
        "B": {"cost": 2.0, "next_hop": "B", "hops": 1},
        "G": {"cost": 10.0, "next_hop": "B", "hops": 4},
    }
    verificar("route hacia un destino conocido", dv.route({"to": "G"}), ["B"])
    verificar("route hacia un destino desconocido devuelve lista vacia",
              dv.route({"to": "Z"}), [])
    verificar("table_rows ordenado por destino",
              dv.table_rows(), [("B", "B", 2.0), ("G", "B", 10.0)])


def prueba_convergencia_topologia_pesada():
    print("\n[8] simulacion completa: intercambio de vectores hasta converger")

    async def simular():
        red = Red()
        nodos = {etq: FakeNode(etq, red, enlaces) for etq, enlaces in PESADA.items()}
        for nodo in nodos.values():
            red.registrar(nodo)
        dvs = {etq: DistanceVector(nodo) for etq, nodo in nodos.items()}

        for dv in dvs.values():
            dv._recompute()

        for _ in range(40):
            for dv in dvs.values():
                await dv._broadcast()

            hubo_cambio = False
            for etq, nodo in nodos.items():
                pendientes, nodo.entrante = nodo.entrante, []
                for pkt in pendientes:
                    antes = dict(dvs[etq].table)
                    await dvs[etq].handle_info(pkt)
                    if dvs[etq].table != antes:
                        hubo_cambio = True

            if not hubo_cambio and not any(n.entrante for n in nodos.values()):
                break

        return dvs

    dvs = asyncio.run(simular())
    tabla_a = dvs["A"].table

    costos = {dest: round(info["cost"], 1) for dest, info in tabla_a.items()}
    verificar("costos de A coinciden con Dijkstra centralizado", costos, ESPERADO_COSTOS)

    saltos = {dest: info["hops"] for dest, info in tabla_a.items()}
    verificar("saltos de A coinciden con la ruta optima", saltos, ESPERADO_HOPS)

    siguiente = {dest: info["next_hop"] for dest, info in tabla_a.items()}
    verificar("todas las rutas optimas desde A pasan por B",
              siguiente, {d: "B" for d in ESPERADO_COSTOS})


def main():
    print("PRUEBAS DE DISTANCE VECTOR ROUTING")
    for prueba in (
        prueba_seleccion_de_ruta,
        prueba_ignora_rutas_envenenadas,
        prueba_limite_de_saltos,
        prueba_vector_saliente_split_horizon,
        prueba_expiracion_de_vectores,
        prueba_handle_info_valida_origen,
        prueba_route_y_table_rows,
        prueba_convergencia_topologia_pesada,
    ):
        prueba()

    print("\n" + "=" * 60)
    if fallos:
        print("RESULTADO: {} prueba(s) fallaron".format(len(fallos)))
        return 1
    print("RESULTADO: todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
