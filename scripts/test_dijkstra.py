"""Pruebas unitarias del nucleo de Dijkstra.

Son deterministas y no levantan red: verifican el algoritmo contra grafos con
respuesta conocida, incluidos los casos borde que suelen romper una
implementacion (nodos inalcanzables, grafos desconectados, empates de costo,
nodo aislado).

Uso:
    python scripts/test_dijkstra.py
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from routing.dijkstra_core import path_to, shortest_paths  # noqa: E402

# Topologia de configs/topo-weighted.txt
PESADA = {
    "A": {"B": 2, "C": 5},
    "B": {"A": 2, "C": 1, "D": 4},
    "C": {"A": 5, "B": 1, "E": 3},
    "D": {"B": 4, "E": 2, "F": 6},
    "E": {"C": 3, "D": 2, "G": 4},
    "F": {"D": 6, "G": 1},
    "G": {"E": 4, "F": 1},
}

fallos = []


def verificar(descripcion, obtenido, esperado):
    if obtenido == esperado:
        print("  OK   {}".format(descripcion))
    else:
        print("  FALLO {}\n        esperado: {!r}\n        obtenido: {!r}".format(
            descripcion, esperado, obtenido))
        fallos.append(descripcion)


def prueba_topologia_pesada():
    print("\n[1] caminos minimos desde A en la topologia con pesos")
    dist, first_hop, previous = shortest_paths(PESADA, "A")

    # Calculados a mano: A-B=2, A-B-C=3, A-B-D=6, A-B-C-E=6,
    # A-B-C-E-G=10, A-B-C-E-G-F=11 (mejor que A-B-D-F=12).
    verificar("distancias", {k: round(v, 1) for k, v in dist.items()},
              {"B": 2.0, "C": 3.0, "D": 6.0, "E": 6.0, "F": 11.0, "G": 10.0})
    verificar("primer salto", first_hop,
              {"B": "B", "C": "B", "D": "B", "E": "B", "F": "B", "G": "B"})
    verificar("ruta A->G", path_to(previous, "A", "G"), ["A", "B", "C", "E", "G"])
    verificar("ruta A->F evita el enlace caro D-F",
              path_to(previous, "A", "F"), ["A", "B", "C", "E", "G", "F"])
    verificar("el origen no aparece en las distancias", "A" in dist, False)


def prueba_sin_C():
    print("\n[2] la misma topologia sin el nodo C (ruta alterna optima)")
    grafo = {n: {v: c for v, c in enlaces.items() if v != "C"}
             for n, enlaces in PESADA.items() if n != "C"}
    dist, _, previous = shortest_paths(grafo, "A")
    verificar("costo A->G sube de 10 a 12", round(dist["G"], 1), 12.0)
    verificar("ruta A->G", path_to(previous, "A", "G"), ["A", "B", "D", "E", "G"])


def prueba_desconectado():
    print("\n[3] grafo desconectado")
    grafo = {"A": {"B": 1}, "B": {"A": 1}, "X": {"Y": 1}, "Y": {"X": 1}}
    dist, first_hop, previous = shortest_paths(grafo, "A")
    verificar("solo se alcanza B", set(dist), {"B"})
    verificar("X no tiene primer salto", "X" in first_hop, False)
    verificar("ruta a un inalcanzable es vacia", path_to(previous, "A", "X"), [])


def prueba_nodo_aislado():
    print("\n[4] nodo sin vecinos activos")
    dist, first_hop, _ = shortest_paths({"A": {}}, "A")
    verificar("sin destinos", dist, {})
    verificar("sin primeros saltos", first_hop, {})


def prueba_empate():
    print("\n[5] empate de costo: se resuelve de forma estable")
    grafo = {"A": {"B": 1, "C": 1}, "B": {"A": 1, "D": 1}, "C": {"A": 1, "D": 1}, "D": {"B": 1, "C": 1}}
    dist, first_hop, _ = shortest_paths(grafo, "A")
    verificar("costo a D", round(dist["D"], 1), 2.0)
    verificar("el primer salto a D es uno de los dos empatados",
              first_hop["D"] in ("B", "C"), True)


def prueba_ruta_directa():
    print("\n[6] vecino directo: el primer salto es el mismo destino")
    _, first_hop, previous = shortest_paths(PESADA, "A")
    verificar("primer salto a B", first_hop["B"], "B")
    verificar("ruta a B", path_to(previous, "A", "B"), ["A", "B"])
    verificar("ruta al propio origen", path_to({}, "A", "A"), ["A"])


def main():
    print("=" * 60)
    print("PRUEBAS DEL NUCLEO DE DIJKSTRA")
    print("=" * 60)
    for prueba in (prueba_topologia_pesada, prueba_sin_C, prueba_desconectado,
                   prueba_nodo_aislado, prueba_empate, prueba_ruta_directa):
        prueba()

    print("\n" + "=" * 60)
    if fallos:
        print("RESULTADO: {} prueba(s) fallaron".format(len(fallos)))
        return 1
    print("RESULTADO: todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
