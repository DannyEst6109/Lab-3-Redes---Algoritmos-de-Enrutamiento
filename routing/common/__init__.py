"""Infraestructura compartida por los algoritmos de enrutamiento.

Nada de lo que hay aqui es un algoritmo: son las piezas que varios de ellos
reutilizan.

    base.py           la interfaz `RoutingAlgorithm` que todos implementan
    shortest_path.py  Dijkstra puro sobre un grafo (lo usan dijkstra.py y lsr.py)
    seen_cache.py     deduplicacion de paquetes (la usan flooding.py y lsr.py)
"""
