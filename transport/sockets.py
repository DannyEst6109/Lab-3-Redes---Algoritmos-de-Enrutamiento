"""Transporte sobre sockets TCP (fase 1: pruebas locales).

Cada nodo levanta un servidor TCP en la direccion `host:puerto` que le asigna
el archivo de nombres, y abre una conexion por paquete hacia sus vecinos.
Los paquetes viajan como una linea de JSON terminada en '\n'.

Se abre una conexion por paquete a proposito: hace que la caida y el reinicio
de un nodo sean transparentes (no hay que reciclar conexiones muertas) y
permite medir el RTT real del enlace con los paquetes HELLO/ECHO.
"""

import asyncio

from core import packet as pk
from transport.base import Transport

CONNECT_TIMEOUT = 2.0
MAX_LINE = 1 << 20  # 1 MiB por paquete es mas que suficiente


def parse_address(address):
    """'127.0.0.1:5001' -> ('127.0.0.1', 5001)."""
    if ":" not in address:
        raise ValueError(
            "direccion invalida para el transporte de sockets: {!r} "
            "(se espera host:puerto)".format(address)
        )
    host, _, port = address.rpartition(":")
    return host, int(port)


class SocketTransport(Transport):
    def __init__(self, node):
        super().__init__(node)
        self._server = None

    async def start(self):
        host, port = parse_address(self.node.address)
        self._server = await asyncio.start_server(self._handle_client, host, port, limit=MAX_LINE)
        self.node.log.info("escuchando en %s:%d", host, port)

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, reader, writer):
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    parsed = pk.decode(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    self.node.log.debug("paquete malformado descartado: %s", exc)
                    continue
                await self.node.on_packet(parsed)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                pass

    async def send(self, address, pkt):
        try:
            host, port = parse_address(address)
        except ValueError as exc:
            self.node.log.error("%s", exc)
            return False

        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
            )
            writer.write(pk.encode(pkt))
            await writer.drain()
            return True
        except (OSError, asyncio.TimeoutError):
            # El vecino esta caido o todavia no arranca: no es un error fatal,
            # el monitor de vecinos se encargara de marcar el enlace como caido.
            self.node.log.debug("no se pudo entregar a %s", address)
            return False
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionResetError, OSError):
                    pass
