"""Interfaz del medio de transporte.

El nodo no sabe (ni le importa) si los paquetes viajan por sockets TCP o por
XMPP. Esa es justamente la razon de esta abstraccion: la fase 1 del
laboratorio se desarrolla con `SocketTransport` y la entrega oficial de la
fase 2 solo cambia la implementacion por `XMPPTransport`.
"""

import abc


class Transport(abc.ABC):
    """Un transporte entrega paquetes a `node.on_packet(pkt)`."""

    def __init__(self, node):
        self.node = node

    @abc.abstractmethod
    async def start(self):
        """Deja el transporte listo para enviar y recibir."""

    @abc.abstractmethod
    async def stop(self):
        """Libera los recursos del transporte."""

    @abc.abstractmethod
    async def send(self, address, pkt):
        """Entrega un paquete a un vecino directo. Devuelve True si se logro."""

    @property
    def local_address(self):
        return self.node.address
