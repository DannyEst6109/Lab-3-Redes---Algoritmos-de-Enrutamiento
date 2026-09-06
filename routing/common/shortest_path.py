"""Algoritmo de Dijkstra (nucleo reutilizable).

Se mantiene deliberadamente libre de red y de estado: recibe un grafo y un
origen, y devuelve distancias y primer salto. Lo usan tanto el modo Dijkstra
puro (que recibe la topologia por configuracion) como Link State Routing (que
la reconstruye a partir de los LSPs recibidos).

Complejidad: O((V + E) log V) usando un heap binario con borrado perezoso.
"""

import heapq

INF = float("inf")


def shortest_paths(graph, source):
    """Calcula caminos minimos desde `source`.

    graph:  {nodo: {vecino: costo}} (dirigido; un enlace bidireccional aparece
            en ambos sentidos)
    return: (dist, first_hop, previous)
            dist      -> {nodo: costo minimo}
            first_hop -> {nodo: primer salto desde source} (el proximo salto
                         que debe escribirse en la tabla de enrutamiento)
            previous  -> {nodo: predecesor} para reconstruir la ruta completa
    """
    dist = {source: 0.0}
    first_hop = {}
    previous = {}
    visited = set()
    heap = [(0.0, source)]

    while heap:
        d, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)

        for neighbor, weight in (graph.get(node) or {}).items():
            if neighbor in visited or weight is None or weight < 0:
                continue
            candidate = d + weight
            if candidate < dist.get(neighbor, INF):
                dist[neighbor] = candidate
                previous[neighbor] = node
                # El primer salto se propaga: los vecinos directos del origen
                # son su propio primer salto, el resto hereda el del predecesor.
                first_hop[neighbor] = neighbor if node == source else first_hop[node]
                heapq.heappush(heap, (candidate, neighbor))

    dist.pop(source, None)
    return dist, first_hop, previous


def path_to(previous, source, target):
    """Reconstruye la ruta completa source -> target, o [] si no hay camino."""
    if target == source:
        return [source]
    path = [target]
    cursor = target
    while cursor in previous:
        cursor = previous[cursor]
        path.append(cursor)
        if cursor == source:
            path.reverse()
            return path
    return []
