"""Interfaz comun de los algoritmos de enrutamiento.

El proceso de forwarding del nodo solo habla con esta interfaz, de modo que
cambiar de algoritmo es cambiar una clase. La separacion sigue la division
que pide el enunciado:

    Forwarding -> decide que hacer con cada paquete que entra o sale
    Routing    -> construye y mantiene la tabla que el forwarding consulta
"""

import abc


class RoutingAlgorithm(abc.ABC):
    #: valor del campo "proto" de los paquetes de esta red
    proto = None

    def __init__(self, node):
        self.node = node
        self.log = node.log

    # ------------------------------------------------------------ ciclo de vida

    async def start(self):
        """Arranca las tareas periodicas del algoritmo (si las tiene)."""

    async def stop(self):
        """Detiene las tareas periodicas."""

    # ------------------------------------------------------------------ eventos

    async def on_neighbor_change(self, event, neighbor):
        """`event` es 'up', 'down' o 'cost'. Dispara la reconvergencia."""

    async def handle_info(self, pkt):
        """Procesa un paquete de tipo INFO (vector de distancias, LSP, tabla)."""

    # ------------------------------------------------------------- forwarding
    def is_duplicate(self, pkt, via=None):
        """True si este paquete ya se proceso y debe descartarse por completo.

        Solo tiene sentido en los algoritmos que inundan la red (Flooding y la
        difusion de LSPs en LSR), donde el mismo paquete llega por varios
        caminos. Descartar aqui evita tanto la entrega repetida al usuario
        como el reenvio ciclico.
        """
        return False


    @abc.abstractmethod
    def route(self, pkt, via=None):
        """Devuelve las direcciones de los vecinos a los que reenviar `pkt`.

        `via` es el vecino por el que llego el paquete (None si se origina
        aqui). Devolver una lista vacia significa descartar el paquete.
        Los algoritmos unicast devuelven a lo sumo un salto; Flooding
        devuelve todos los vecinos activos menos aquel por el que llego.
        """

    # ------------------------------------------------------------- inspeccion

    def table_rows(self):
        """[(destino, siguiente_salto, costo)] para el comando `table`."""
        return []

    def describe(self):
        """Texto adicional del estado interno para depuracion."""
        return ""
