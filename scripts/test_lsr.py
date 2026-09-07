import asyncio
import logging
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core import packet as pk
from routing.lsr import BROADCAST, LSP_LIFETIME, LinkStateRouting

logging.disable(logging.CRITICAL)

# Misma topologia de configs/topo-weighted.txt que usan test_dijkstra.py y test_dvr.py
PESADA = {
    "A": {"B": 2, "C": 5},
    "B": {"A": 2, "C": 1, "D": 4},
    "C": {"A": 5, "B": 1, "E": 3},
    "D": {"B": 4, "E": 2, "F": 6},
    "E": {"C": 3, "D": 2, "G": 4},
    "F": {"D": 6, "G": 1},
    "G": {"E": 4, "F": 1},
}

# Respuesta conocida desde A, verificada con Dijkstra centralizado en test_dijkstra.py
ESPERADO_COSTOS = {"B": 2.0, "C": 3.0, "D": 6.0, "E": 6.0, "F": 11.0, "G": 10.0}

fallos = []


def verificar(descripcion, obtenido, esperado):
    if obtenido == esperado:
        print("  OK   {}".format(descripcion))
    else:
        print("  FALLO {}\n        esperado: {!r}\n        obtenido: {!r}".format(
            descripcion, esperado, obtenido))
        fallos.append(descripcion)


class FakeNeighbors:
    # sustituye a core.neighbors.NeighborTable con costos fijos controlables
    def __init__(self, costs):
        self._costs = dict(costs)
        self._alive = {addr: True for addr in costs}

    def is_neighbor(self, addr):
        return addr in self._costs

    def alive_costs(self):
        return {a: float(c) for a, c in self._costs.items() if self._alive.get(a)}

    def alive_addresses(self):
        return [a for a in self._costs if self._alive.get(a)]

    def all(self):
        return []

    def set_alive(self, addr, alive):
        self._alive[addr] = alive


class Red:
    # red en memoria: entrega lo que un FakeNode manda con send_direct
    def __init__(self):
        self.nodos = {}

    def registrar(self, nodo):
        self.nodos[nodo.address] = nodo


class FakeNode:
    # sustituye a core.node.Node: solo lo que LinkStateRouting necesita
    def __init__(self, address, red, neighbor_costs):
        self.address = address
        self.red = red
        self.log = logging.getLogger("test-lsr-" + address)
        self.neighbors = FakeNeighbors(neighbor_costs)
        self.entrante = []
        self.enviados = []

    def label_of(self, addr):
        return addr

    async def send_direct(self, address, pkt):
        pk.set_header(pkt, "via", self.address)
        self.enviados.append((address, pkt))
        destino = self.red.nodos.get(address)
        if destino is not None:
            destino.entrante.append(dict(pkt))


def hacer_lsr(address, neighbor_costs, red=None):
    nodo = FakeNode(address, red or Red(), neighbor_costs)
    return LinkStateRouting(nodo), nodo


def lsp_de(origin, seq, links, ttl=8, mid=None):
    return pk.make_packet(
        proto=pk.PROTO_LSR, ptype=pk.TYPE_INFO, frm=origin, to=BROADCAST,
        payload={"kind": "lsp", "origin": origin, "seq": seq, "links": links},
        ttl=ttl, headers=[{"mid": mid or pk.new_id()}],
    )


def prueba_emision_del_lsp_propio():
    print("\n[1] _originate anuncia mis enlaces vivos y sube la secuencia")

    async def cuerpo():
        lsr, nodo = hacer_lsr("A", {"B": 2, "C": 5})
        red = nodo.red
        red.registrar(nodo)
        await lsr._originate()

        verificar("la secuencia arranca en 1", lsr.seq, 1)
        verificar("la LSDB contiene mi propia entrada",
                  lsr.lsdb["A"]["links"], {"B": 2.0, "C": 5.0})
        verificar("el LSP se mando a todos los vecinos vivos",
                  sorted(addr for addr, _ in nodo.enviados), ["B", "C"])

        _, pkt = nodo.enviados[0]
        verificar("el LSP viaja como paquete info", pkt["type"], pk.TYPE_INFO)
        verificar("el payload declara kind=lsp", pkt["payload"]["kind"], "lsp")

        nodo.neighbors.set_alive("C", False)
        nodo.enviados.clear()
        await lsr._originate()
        verificar("un enlace caido desaparece del LSP siguiente",
                  lsr.lsdb["A"]["links"], {"B": 2.0})
        verificar("la secuencia avanza en cada emision", lsr.seq, 2)

    asyncio.run(cuerpo())


def prueba_secuencia_corta_la_inundacion():
    print("\n[2] un LSP con secuencia vieja o repetida no se guarda ni se reinunda")

    async def cuerpo():
        lsr, nodo = hacer_lsr("A", {"B": 2, "C": 5})
        nodo.red.registrar(nodo)

        await lsr.handle_info(lsp_de("D", 5, {"B": 4.0}))
        verificar("el primer LSP de D se acepta", lsr.lsdb["D"]["seq"], 5)
        verificar("y se reinunda a los vecinos",
                  sorted(addr for addr, _ in nodo.enviados), ["B", "C"])

        nodo.enviados.clear()
        await lsr.handle_info(lsp_de("D", 4, {"B": 99.0}))
        verificar("un LSP con secuencia menor se descarta", lsr.lsdb["D"]["seq"], 5)
        verificar("y no se reinunda", nodo.enviados, [])

        await lsr.handle_info(lsp_de("D", 5, {"B": 99.0}))
        verificar("un LSP con la misma secuencia tampoco se acepta",
                  lsr.lsdb["D"]["links"], {"B": 4.0})

        nodo.enviados.clear()
        await lsr.handle_info(lsp_de("D", 6, {"B": 4.0, "E": 2.0}))
        verificar("un LSP mas nuevo si reemplaza al anterior",
                  lsr.lsdb["D"]["links"], {"B": 4.0, "E": 2.0})
        verificar("y vuelve a inundarse",
                  sorted(addr for addr, _ in nodo.enviados), ["B", "C"])

    asyncio.run(cuerpo())


def prueba_reinundacion_excluye_el_enlace_de_entrada():
    print("\n[3] el LSP se reenvia a todos los vecinos menos por donde llego")

    async def cuerpo():
        lsr, nodo = hacer_lsr("A", {"B": 2, "C": 5})
        nodo.red.registrar(nodo)

        pkt = lsp_de("D", 1, {"B": 4.0}, ttl=8)
        pk.set_header(pkt, "via", "B")
        await lsr.handle_info(pkt)

        destinos = [addr for addr, _ in nodo.enviados]
        verificar("no se devuelve por el vecino de entrada", destinos, ["C"])
        verificar("el TTL se decrementa en el reenvio", nodo.enviados[0][1]["ttl"], 7)

        nodo.enviados.clear()
        agotado = lsp_de("E", 1, {"D": 2.0}, ttl=1)
        pk.set_header(agotado, "via", "B")
        await lsr.handle_info(agotado)
        verificar("un LSP con el TTL agotado se guarda pero ya no se reenvia",
                  ("E" in lsr.lsdb, nodo.enviados), (True, []))

    asyncio.run(cuerpo())


def prueba_lsp_propio_reflejado():
    print("\n[4] el LSP propio que vuelve por la red se ignora y adelanta el contador")

    async def cuerpo():
        lsr, nodo = hacer_lsr("A", {"B": 2})
        nodo.red.registrar(nodo)
        lsr.seq = 3

        propio = lsp_de("A", 9, {"B": 2.0})
        pk.set_header(propio, "via", "B")
        await lsr.handle_info(propio)

        verificar("no se reinunda el LSP propio", nodo.enviados, [])
        verificar("el contador se adelanta a la secuencia vista", lsr.seq, 9)

        await lsr.handle_info(lsp_de("A", 2, {"B": 2.0}))
        verificar("una secuencia menor no retrocede el contador", lsr.seq, 9)

    asyncio.run(cuerpo())


def prueba_enlaces_unilaterales():
    print("\n[5] un enlace que solo declara un extremo no entra en el grafo")
    lsr, _ = hacer_lsr("A", {"B": 2})
    ahora = time.monotonic()
    lsr.lsdb = {
        "A": {"seq": 1, "links": {"B": 2.0}, "ts": ahora},
        "B": {"seq": 1, "links": {"A": 2.0}, "ts": ahora},
        # C dice tener enlace con B, pero B no lo reconoce: no debe usarse
        "C": {"seq": 1, "links": {"B": 1.0, "Z": 7.0}, "ts": ahora},
    }
    grafo = lsr._build_graph()

    verificar("el enlace bidireccional A-B se conserva", grafo["A"], {"B": 2.0})
    verificar("el enlace unilateral C-B se descarta", grafo["C"], {"Z": 7.0})

    lsr._recompute()
    verificar("C no es alcanzable con la LSDB a medio converger",
              "C" in lsr.next_hop, False)


def prueba_expiracion_de_lsp():
    print("\n[6] un LSP que deja de refrescarse se saca de la LSDB (nodo caido)")
    lsr, _ = hacer_lsr("A", {"B": 2})
    ahora = time.monotonic()
    lsr.lsdb = {
        "A": {"seq": 1, "links": {"B": 2.0}, "ts": ahora - (LSP_LIFETIME + 10)},
        "B": {"seq": 1, "links": {"A": 2.0}, "ts": ahora},
        "D": {"seq": 1, "links": {"B": 4.0}, "ts": ahora - (LSP_LIFETIME + 5)},
    }
    vencio = lsr._expire_stale()

    verificar("el LSP viejo de D se elimina", "D" in lsr.lsdb, False)
    verificar("el LSP fresco de B se conserva", "B" in lsr.lsdb, True)
    verificar("mi propia entrada nunca expira", "A" in lsr.lsdb, True)
    verificar("se reporta que hubo cambios para recalcular", vencio, True)


def prueba_route_y_table_rows():
    print("\n[7] route() y table_rows() leen el resultado de Dijkstra")
    lsr, nodo = hacer_lsr("A", {"B": 2, "C": 5})
    lsr.next_hop = {"B": "B", "G": "B"}
    lsr.dist = {"B": 2.0, "G": 10.0}

    verificar("route hacia un destino conocido", lsr.route({"to": "G"}), ["B"])
    verificar("route hacia un destino desconocido devuelve lista vacia",
              lsr.route({"to": "Z"}), [])
    verificar("table_rows ordenado por destino",
              lsr.table_rows(), [("B", "B", 2.0), ("G", "B", 10.0)])

    lsr.next_hop = {}
    verificar("respaldo: un vecino directo vivo se alcanza aunque no haya tabla",
              lsr.route({"to": "C"}), ["C"])


def prueba_convergencia_topologia_pesada():
    print("\n[8] simulacion completa: inundacion de LSP hasta converger")

    async def simular():
        red = Red()
        nodos = {etq: FakeNode(etq, red, enlaces) for etq, enlaces in PESADA.items()}
        for nodo in nodos.values():
            red.registrar(nodo)
        lsrs = {etq: LinkStateRouting(nodo) for etq, nodo in nodos.items()}

        for lsr in lsrs.values():
            await lsr._originate()

        for _ in range(40):
            pendientes = {etq: nodo.entrante for etq, nodo in nodos.items()}
            for nodo in nodos.values():
                nodo.entrante = []
            if not any(pendientes.values()):
                break
            for etq, paquetes in pendientes.items():
                for pkt in paquetes:
                    await lsrs[etq].handle_info(pkt)

        return lsrs

    lsrs = asyncio.run(simular())
    lsr_a = lsrs["A"]

    verificar("la LSDB de A conoce a los 7 nodos", len(lsr_a.lsdb), 7)

    costos = {dest: round(costo, 1) for dest, costo in lsr_a.dist.items()}
    verificar("costos de A coinciden con Dijkstra centralizado", costos, ESPERADO_COSTOS)

    verificar("todas las rutas optimas desde A pasan por B",
              lsr_a.next_hop, {d: "B" for d in ESPERADO_COSTOS})

    verificar("la LSDB de G tambien converge a los 7 nodos", len(lsrs["G"].lsdb), 7)
    verificar("G alcanza A con el mismo costo (enlaces simetricos)",
              round(lsrs["G"].dist["A"], 1), 10.0)


def main():
    print("PRUEBAS DE LINK STATE ROUTING")
    for prueba in (
        prueba_emision_del_lsp_propio,
        prueba_secuencia_corta_la_inundacion,
        prueba_reinundacion_excluye_el_enlace_de_entrada,
        prueba_lsp_propio_reflejado,
        prueba_enlaces_unilaterales,
        prueba_expiracion_de_lsp,
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