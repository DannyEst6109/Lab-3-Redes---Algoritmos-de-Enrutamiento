"""Flooding  ---  PENDIENTE DE IMPLEMENTAR

Responsable: (anotar aqui el nombre del integrante)

================================================================================
QUE ES
================================================================================
El algoritmo mas simple de los cuatro. Un nodo que recibe un paquete que no es
para el lo reenvia por *todos* sus enlaces activos, salvo por aquel por el que
le llego. No construye tabla de enrutamiento: su unica entrada es la lista de
vecinos.

Segun el enunciado, su unico input es "conocimiento de sus vecinos solamente".

================================================================================
QUE HAY QUE IMPLEMENTAR
================================================================================
Solo dos metodos son imprescindibles:

    route(pkt, via)          -> a que vecinos reenviar el paquete
    is_duplicate(pkt, via)   -> si este paquete ya se vio y hay que descartarlo

Los demas ganchos de `RoutingAlgorithm` (start, stop, on_neighbor_change,
handle_info) no hacen falta: Flooding no mantiene estado de red ni intercambia
paquetes de informacion.

================================================================================
LO QUE HAY QUE CUIDAR
================================================================================
1. CICLOS. Sin deduplicacion, en una topologia con un solo ciclo el numero de
   copias crece exponencialmente. Cada mensaje viaja con un identificador unico
   en la cabecera `mid`; si ya se vio ese `mid`, el paquete se descarta por
   completo (ni se entrega al usuario ni se reenvia).

   Para eso esta `routing.common.seen_cache.SeenCache`, que ya maneja la
   expiracion de entradas:

       self.seen = SeenCache()
       ...
       es_nuevo = self.seen.check_and_add(mid)

2. NO DEVOLVER EL PAQUETE POR DONDE LLEGO. El parametro `via` de `route()` trae
   la direccion del vecino que hizo el ultimo salto. Hay que excluirlo de la
   lista de destinos.

3. SOLO VECINOS VIVOS. `self.node.neighbors.alive_addresses()` devuelve las
   direcciones de los vecinos que estan respondiendo los HELLO. Reenviar a un
   vecino caido es trafico perdido.

4. EL TTL YA LO MANEJA EL NODO. `core/node.py` decrementa el TTL y descarta el
   paquete cuando llega a cero, antes de llamar a `route()`. No hay que
   duplicar esa logica aqui.

5. OPTIMIZACION OPCIONAL (suma para el criterio de "eficiente y optimizada"):
   si el destino del paquete es un vecino directo y activo, se le puede
   entregar solo a el en vez de inundar toda la red. Es una decision local que
   no altera el protocolo.

================================================================================
QUE MOSTRAR EN LA CONSOLA
================================================================================
`table_rows()` y `describe()` son opcionales pero valen la pena para la demo.
Flooding no tiene tabla de enrutamiento, asi que `table_rows()` puede devolver
la lista de vecinos activos, y `describe()` contadores utiles (paquetes
originados, reenviados y duplicados descartados).

================================================================================
COMO PROBARLO
================================================================================
1. Registrar la clase en el diccionario ALGORITMOS de `node.py`.
2. python scripts/test_network.py --algo flooding --topo configs/topo-weighted.txt
"""

from core import packet as pk
from routing.common.base import RoutingAlgorithm
from routing.common.seen_cache import SeenCache  # noqa: F401  (guia de uso)


class Flooding(RoutingAlgorithm):
    proto = pk.PROTO_FLOODING

    def __init__(self, node):
        super().__init__(node)
        # TODO: inicializar la cache de paquetes vistos y los contadores.

    def is_duplicate(self, pkt, via=None):
        # TODO: leer la cabecera `mid` con pk.get_header(pkt, "mid") y decidir
        #       si el paquete ya se proceso.
        return False

    def route(self, pkt, via=None):
        # TODO: devolver la lista de direcciones de vecinos a los que reenviar.
        raise NotImplementedError(
            "Flooding.route() todavia no esta implementado (routing/flooding.py)"
        )
