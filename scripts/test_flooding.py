"""Pruebas unitarias de Flooding.

Igual que `test_dijkstra.py`, son deterministas y no levantan red: en vez de
un `Node`/`NeighborTable` reales (que dependen de sockets/asyncio), se usan
dobles minimos que solo exponen lo que `Flooding` necesita:

    node.address
    node.label
    node.log
    node.neighbors.all()
    node.neighbors.alive_addresses()

Uso:
    python scripts/test_flooding.py
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core import packet as pk  # noqa: E402
from routing.flooding import Flooding  # noqa: E402

fallos = []


def verificar(descripcion, obtenido, esperado):
    if obtenido == esperado:
        print("  OK   {}".format(descripcion))
    else:
        print("  FALLO {}\n        esperado: {!r}\n        obtenido: {!r}".format(
            descripcion, esperado, obtenido))
        fallos.append(descripcion)


# --------------------------------------------------------------------------
# dobles de prueba: lo minimo que Flooding necesita de node/neighbors
# --------------------------------------------------------------------------

class FakeLog:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


class FakeNeighbor:
    def __init__(self, address, label, alive=True, cost=1.0):
        self.address = address
        self.label = label
        self.alive = alive
        self.cost = cost


class FakeNeighborTable:
    def __init__(self, neighbors):
        self._neighbors = list(neighbors)

    def all(self):
        return list(self._neighbors)

    def alive_addresses(self):
        return [n.address for n in self._neighbors if n.alive]


class FakeNode:
    def __init__(self, address, label, neighbors):
        self.address = address
        self.label = label
        self.log = FakeLog()
        self.neighbors = FakeNeighborTable(neighbors)


def make_flooding(vecinos):
    """vecinos: [(address, label, alive, cost)] -> (Flooding, FakeNode)"""
    node = FakeNode(
        "a@x", "A",
        [FakeNeighbor(addr, lbl, alive, cost) for addr, lbl, alive, cost in vecinos],
    )
    return Flooding(node), node


def msg(to="z@x", mid="m1", via=None):
    pkt = pk.make_packet(
        proto=pk.PROTO_FLOODING, ptype=pk.TYPE_MESSAGE,
        frm="a@x", to=to, payload="hola", ttl=pk.DEFAULT_TTL,
        headers=[{"mid": mid}],
    )
    if via is not None:
        pk.set_header(pkt, "via", via)
    return pkt


# --------------------------------------------------------------------------
# pruebas
# --------------------------------------------------------------------------

def prueba_inunda_a_todos_los_vivos():
    print("\n[1] al originar (via=None) se reenvia a todos los vecinos vivos")
    flooding, _ = make_flooding([
        ("b@x", "B", True, 1.0),
        ("c@x", "C", True, 1.0),
        ("d@x", "D", False, 1.0),  # caido
    ])
    destinos = flooding.route(msg(to="z@x"), via=None)
    verificar("solo los vivos, D queda fuera", sorted(destinos), ["b@x", "c@x"])


def prueba_no_reenvia_por_donde_llego():
    print("\n[2] no se reenvia de vuelta por el enlace 'via'")
    flooding, _ = make_flooding([
        ("b@x", "B", True, 1.0),
        ("c@x", "C", True, 1.0),
    ])
    destinos = flooding.route(msg(to="z@x"), via="b@x")
    verificar("se excluye a B", destinos, ["c@x"])


def prueba_entrega_directa_a_vecino():
    print("\n[3] optimizacion: si el destino es vecino vivo, se le entrega solo a el")
    flooding, _ = make_flooding([
        ("b@x", "B", True, 1.0),
        ("c@x", "C", True, 1.0),
    ])
    destinos = flooding.route(msg(to="b@x"), via="c@x")
    verificar("entrega directa, no se inunda al resto", destinos, ["b@x"])


def prueba_vecino_caido_nunca_recibe():
    print("\n[4] un vecino caido no aparece nunca como destino, ni como entrega directa")
    flooding, _ = make_flooding([
        ("b@x", "B", False, 1.0),
        ("c@x", "C", True, 1.0),
    ])
    destinos_flood = flooding.route(msg(to="z@x"), via=None)
    destinos_directo = flooding.route(msg(to="b@x"), via=None)
    verificar("flooding evita a B (caido)", destinos_flood, ["c@x"])
    verificar("tampoco se le entrega directo si esta caido", destinos_directo, ["c@x"])


def prueba_duplicados_se_descartan():
    print("\n[5] el segundo paquete con el mismo mid se marca como duplicado")
    flooding, _ = make_flooding([("b@x", "B", True, 1.0)])
    primero = flooding.is_duplicate(msg(mid="m1"))
    segundo = flooding.is_duplicate(msg(mid="m1"))
    verificar("la primera vez no es duplicado", primero, False)
    verificar("la segunda vez si es duplicado", segundo, True)
    verificar("se cuenta el duplicado", flooding.stats["duplicados"], 1)


def prueba_mids_distintos_no_son_duplicados():
    print("\n[6] mids distintos no interfieren entre si")
    flooding, _ = make_flooding([("b@x", "B", True, 1.0)])
    r1 = flooding.is_duplicate(msg(mid="m1"))
    r2 = flooding.is_duplicate(msg(mid="m2"))
    verificar("m1 es nuevo", r1, False)
    verificar("m2 tambien es nuevo (mid distinto)", r2, False)


def prueba_paquete_sin_mid_no_se_deduplica():
    print("\n[7] sin cabecera 'mid' no se puede deduplicar: nunca se marca duplicado")
    flooding, _ = make_flooding([("b@x", "B", True, 1.0)])
    pkt = pk.make_packet(proto=pk.PROTO_FLOODING, ptype=pk.TYPE_MESSAGE,
                         frm="a@x", to="z@x", payload="hola", ttl=pk.DEFAULT_TTL)
    r1 = flooding.is_duplicate(pkt)
    r2 = flooding.is_duplicate(pkt)
    verificar("primera vez sin mid: no es duplicado", r1, False)
    verificar("segunda vez sin mid: tampoco (no se puede saber)", r2, False)
    verificar("no se cuenta como duplicado", flooding.stats["duplicados"], 0)


def prueba_contadores_originado_vs_reenviado():
    print("\n[8] los contadores distinguen mensajes propios de reenvios")
    flooding, _ = make_flooding([
        ("b@x", "B", True, 1.0),
        ("c@x", "C", True, 1.0),
    ])
    flooding.route(msg(to="z@x"), via=None)       # originado aqui
    flooding.route(msg(to="z@x"), via="b@x")       # reenviado
    flooding.route(msg(to="z@x"), via="c@x")       # reenviado
    verificar("un mensaje originado", flooding.stats["originados"], 1)
    verificar("dos mensajes reenviados", flooding.stats["reenviados"], 2)


def prueba_table_rows_solo_vivos():
    print("\n[9] table_rows() solo muestra vecinos activos")
    flooding, _ = make_flooding([
        ("b@x", "B", True, 2.5),
        ("d@x", "D", False, 1.0),
    ])
    filas = flooding.table_rows()
    verificar("solo aparece B (vivo)", filas, [("B", "B", 2.5)])


def prueba_sin_vecinos_vivos_no_hay_destinos():
    print("\n[10] nodo aislado (todos los vecinos caidos): no hay a donde reenviar")
    flooding, _ = make_flooding([
        ("b@x", "B", False, 1.0),
        ("c@x", "C", False, 1.0),
    ])
    destinos = flooding.route(msg(to="z@x"), via=None)
    verificar("lista vacia", destinos, [])


def main():
    print("=" * 60)
    print("PRUEBAS DE FLOODING")
    print("=" * 60)
    for prueba in (
        prueba_inunda_a_todos_los_vivos,
        prueba_no_reenvia_por_donde_llego,
        prueba_entrega_directa_a_vecino,
        prueba_vecino_caido_nunca_recibe,
        prueba_duplicados_se_descartan,
        prueba_mids_distintos_no_son_duplicados,
        prueba_paquete_sin_mid_no_se_deduplica,
        prueba_contadores_originado_vs_reenviado,
        prueba_table_rows_solo_vivos,
        prueba_sin_vecinos_vivos_no_hay_destinos,
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