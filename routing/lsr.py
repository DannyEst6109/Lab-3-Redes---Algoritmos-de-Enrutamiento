"""Link State Routing  ---  PENDIENTE DE IMPLEMENTAR

Responsable: (anotar aqui el nombre del integrante)

================================================================================
QUE ES
================================================================================
A diferencia de DVR, aqui cada nodo termina conociendo el mapa completo de la
red y calcula sus rutas por su cuenta. Funciona en dos tiempos:

  1. Cada nodo anuncia unicamente el estado de SUS PROPIOS enlaces en un LSP
     (Link State Packet), y ese LSP se inunda por toda la red. Al recibir los
     LSPs de todos, cada nodo reconstruye la topologia en una base de datos
     local (LSDB).
  2. Sobre esa topologia reconstruida corre Dijkstra y obtiene el siguiente
     salto hacia cada destino.

Segun el enunciado, su input son "las Tablas de los demas Nodos (de ella se
deriva la Topologia)".

IMPORTANTE: el enunciado pide explicitamente que este algoritmo REUTILICE
Flooding y Dijkstra en vez de reimplementarlos. Las dos piezas ya existen:

    routing.common.shortest_path.shortest_paths()   -> Dijkstra
    routing.flooding.Flooding                       -> para difundir los LSPs
    routing.common.seen_cache.SeenCache             -> deduplicacion

================================================================================
QUE HAY QUE IMPLEMENTAR
================================================================================
    start() / stop()         tarea periodica que reemite el LSP propio y
                             envejece los ajenos
    handle_info(pkt)         recibir un LSP, guardarlo, recalcular y reinundarlo
    on_neighbor_change(...)  si cambian mis enlaces, cambia mi LSP: reemitirlo
    route(pkt, via)          devolver [siguiente_salto] segun Dijkstra
    table_rows()             para el comando `table` de la consola

================================================================================
FORMATO SUGERIDO DEL LSP
================================================================================
Tipo `info`, inundado por toda la red (ttl alto, cabecera `mid` para deduplicar):

    payload = {"kind": "lsp",
               "origin": direccion_del_que_lo_origina,
               "seq": numero_de_secuencia,
               "links": {direccion_vecina: costo, ...}}

Igual que en DVR, este formato hay que acordarlo con los otros grupos para que
haya interoperabilidad.

================================================================================
LO QUE HAY QUE CUIDAR
================================================================================
1. QUE LA INUNDACION TERMINE. Un LSP se reenvia a todos los vecinos menos por
   donde llego, asi que en una topologia con ciclos vuelve una y otra vez. El
   NUMERO DE SECUENCIA es lo que corta el ciclo: si llega un LSP de un origen
   con secuencia menor o igual a la que ya se tiene guardada, se descarta y NO
   se reenvia. Solo los LSP mas nuevos se propagan.

2. ENVEJECIMIENTO. Un nodo que se cae deja de reemitir su LSP, pero el ultimo
   que mando sigue en la LSDB de todos, manteniendolo en la topologia como si
   nada. Hay que descartar los LSP que no se refrescan en cierto tiempo.

3. ENLACES A MEDIO CONVERGER. Durante la convergencia puede pasar que A diga
   "tengo un enlace a B" pero el LSP de B todavia no llego, o ya no incluya a
   A. Meter ese enlace al grafo produce agujeros negros: rutas calculadas sobre
   enlaces que no existen. Conviene exigir que AMBOS extremos declaren el
   enlace antes de usarlo (o aceptarlo provisionalmente solo mientras no se
   conozca el LSP del otro extremo).

4. EL LSP PROPIO DE VUELTA. Un nodo va a recibir su propio LSP reflejado por la
   red. Hay que ignorarlo; y si vuelve con una secuencia mayor que la actual
   (tipico despues de reiniciar el nodo), conviene adelantar el contador propio
   para que la red acepte los anuncios nuevos.

5. RECALCULAR EN EL MOMENTO CORRECTO. Dijkstra debe correr cada vez que cambia
   la LSDB: al aceptar un LSP nuevo, al emitir el propio y al envejecer uno.

6. CONCURRENCIA. La tarea periodica y `handle_info()` tocan la LSDB al mismo
   tiempo; protegerla con un `asyncio.Lock`.

================================================================================
COMO SE USA shortest_paths()
================================================================================
    from routing.common.shortest_path import shortest_paths

    grafo = {...}   # {direccion: {direccion_vecina: costo}} armado desde la LSDB
    dist, first_hop, previous = shortest_paths(grafo, self.node.address)

    dist       -> {destino: costo minimo}
    first_hop  -> {destino: siguiente salto}   <- esto ES la tabla de ruteo
    previous   -> para reconstruir la ruta completa con path_to()

================================================================================
COMO PROBARLO
================================================================================
1. Registrar la clase en el diccionario ALGORITMOS de `node.py`.
2. python scripts/test_network.py --algo lsr --topo configs/topo-weighted.txt

   Con esa topologia, la tabla del nodo A debe converger a costo 10 hacia G,
   por la ruta A-B-C-E-G, identica a la de Dijkstra centralizado. La consola
   tambien acepta `info`, util para ver si la LSDB tiene los 7 nodos.
"""

from core import packet as pk
from routing.common.base import RoutingAlgorithm
from routing.common.shortest_path import shortest_paths  # noqa: F401  (guia de uso)


class LinkStateRouting(RoutingAlgorithm):
    proto = pk.PROTO_LSR

    def __init__(self, node):
        super().__init__(node)
        #: base de datos de estado de enlace
        #: {origen: {"seq": int, "links": {vecino: costo}, "ts": ...}}
        self.lsdb = {}
        #: numero de secuencia de mis propios LSP
        self.seq = 0
        #: resultado de Dijkstra sobre la LSDB
        self.next_hop = {}
        # TODO: preparar la tarea periodica, el lock y el componente de
        #       Flooding que se usara para difundir los LSPs.

    async def start(self):
        # TODO: emitir el primer LSP y lanzar la tarea periodica.
        pass

    async def stop(self):
        # TODO: cancelar la tarea periodica.
        pass

    async def on_neighbor_change(self, event, neighbor):
        # TODO: mis enlaces cambiaron -> emitir un LSP nuevo.
        pass

    async def handle_info(self, pkt):
        # TODO: validar el LSP, comparar el numero de secuencia, guardarlo en
        #       la LSDB, recalcular Dijkstra y reinundarlo a los vecinos.
        pass

    def route(self, pkt, via=None):
        # TODO: buscar el destino en self.next_hop y devolver [siguiente_salto].
        raise NotImplementedError(
            "LinkStateRouting.route() todavia no esta implementado (routing/lsr.py)"
        )

    def table_rows(self):
        # TODO: devolver [(destino, siguiente_salto, costo)] con etiquetas
        #       legibles usando self.node.label_of().
        return []
