"""Distance Vector Routing  ---  PENDIENTE DE IMPLEMENTAR

Responsable: (anotar aqui el nombre del integrante)

================================================================================
QUE ES
================================================================================
Bellman-Ford distribuido. Ningun nodo llega a ver el mapa de la red: cada uno
conoce el costo hacia sus vecinos directos y el vector de distancias que estos
le anuncian, y con eso calcula:

    D(x, y) = min sobre v vecino de [ c(x, v) + D(v, y) ]

Luego publica su propio vector a los vecinos. La informacion se propaga de
vecino en vecino hasta que la red converge.

Segun el enunciado, su input son "las Tablas de los Vecinos".

================================================================================
QUE HAY QUE IMPLEMENTAR
================================================================================
    start() / stop()         tarea periodica que reanuncia el vector
    handle_info(pkt)         recibir el vector de un vecino y recalcular
    on_neighbor_change(...)  reaccionar a un vecino que se cae, sube o cambia
                             de costo
    route(pkt, via)          devolver [siguiente_salto] segun la tabla
    table_rows()             para el comando `table` de la consola

`is_duplicate()` no se usa: DVR no inunda nada, los anuncios van solo a los
vecinos directos (ttl=1).

================================================================================
FORMATO SUGERIDO DEL PAQUETE DE ANUNCIO
================================================================================
Tipo `info`, enviado a cada vecino con ttl=1:

    payload = {"kind": "dv", "vector": {direccion_destino: costo, ...}}

OJO: este formato hay que acordarlo con los otros grupos. El enunciado pide que
haya interoperabilidad entre codigos de distintos grupos en un mismo algoritmo,
y el contenido del payload es justamente lo que el enunciado no fija.

================================================================================
LO QUE HAY QUE CUIDAR
================================================================================
1. COUNT TO INFINITY. Es el problema clasico del algoritmo: cuando un enlace
   cae, dos nodos pueden alimentarse mutuamente rutas que ya no existen,
   subiendo el costo de a poco y sin parar. Dos defensas, y conviene poner
   las dos:

   - SPLIT HORIZON CON POISON REVERSE: a un vecino no se le anuncia como
     alcanzable un destino cuyo siguiente salto es el mismo. Se le anuncia
     envenenado, con costo infinito. Para saber por donde llego un paquete
     esta la cabecera `via`; para saber el siguiente salto de cada destino,
     la propia tabla.

   - LIMITE DE SALTOS: una ruta que supera cierto numero de saltos se declara
     inalcanzable. RIP usa 16.

     CUIDADO CON ESTO: aqui el costo de un enlace es el RTT en milisegundos,
     no un conteo de saltos. Un umbral sobre el *costo* (del estilo "si cuesta
     mas de 16 es inalcanzable") declara inalcanzables rutas perfectamente
     validas, porque un enlace normal ya cuesta 10 o 20 ms. El limite tiene
     que ser sobre el numero de saltos, lo cual implica anunciarlo junto al
     costo. El infinito de costo es un centinela aparte (p. ej. 1e9, porque
     JSON no tiene infinito).

2. RUTAS ZOMBI. Si un vecino deja de anunciar (se cayo), su vector se queda
   guardado y sigue produciendo rutas que ya no existen. Hay que hacerlo
   caducar por tiempo y descartarlo.

3. VALIDAR EL ORIGEN. Un vector solo es valido si viene de un vecino directo:
   `self.node.neighbors.is_neighbor(pkt["from"])`.

4. TRIGGERED UPDATES. Ademas del anuncio periodico, conviene reanunciar en
   cuanto la tabla cambie. Sin eso la convergencia es notablemente mas lenta.

5. CONCURRENCIA. `handle_info()` y la tarea periodica pueden tocar la tabla al
   mismo tiempo. Un `asyncio.Lock` alrededor del recalculo evita estados
   inconsistentes.

================================================================================
HERRAMIENTAS DISPONIBLES
================================================================================
    self.node.neighbors.alive_costs()      -> {direccion: costo} enlaces vivos
    self.node.neighbors.is_neighbor(dir)   -> bool
    self.node.send_direct(direccion, pkt)  -> enviar a un vecino directo
    self.node.address                      -> mi propia direccion
    self.node.label_of(direccion)          -> "B", para logs legibles

================================================================================
COMO PROBARLO
================================================================================
1. Registrar la clase en el diccionario ALGORITMOS de `node.py`.
2. python scripts/test_network.py --algo dvr --topo configs/topo-weighted.txt

   Con esa topologia, la tabla del nodo A debe converger a costo 10 hacia G,
   por la ruta A-B-C-E-G. Es la misma respuesta que da Dijkstra centralizado:
   si no coincide, hay un error.
"""

from core import packet as pk
from routing.common.base import RoutingAlgorithm


class DistanceVector(RoutingAlgorithm):
    proto = pk.PROTO_DVR

    def __init__(self, node):
        super().__init__(node)
        #: {destino: (costo, siguiente_salto, ...)}
        self.table = {}
        #: vectores recibidos de cada vecino, con su marca de tiempo
        self.received = {}
        # TODO: preparar la tarea periodica y el lock.

    async def start(self):
        # TODO: lanzar la tarea que reanuncia el vector cada cierto tiempo.
        pass

    async def stop(self):
        # TODO: cancelar la tarea periodica.
        pass

    async def on_neighbor_change(self, event, neighbor):
        # TODO: `event` es "up", "down" o "cost". Recalcular y reanunciar.
        pass

    async def handle_info(self, pkt):
        # TODO: validar que venga de un vecino, guardar su vector,
        #       recalcular la tabla y reanunciar si cambio.
        pass

    def route(self, pkt, via=None):
        # TODO: buscar el destino en la tabla y devolver [siguiente_salto].
        raise NotImplementedError(
            "DistanceVector.route() todavia no esta implementado (routing/dvr.py)"
        )

    def table_rows(self):
        # TODO: devolver [(destino, siguiente_salto, costo)] con etiquetas
        #       legibles usando self.node.label_of().
        return []
