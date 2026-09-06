"""Punto de entrada de un nodo de la red.

Ejemplos:

    # fase 1 (sockets TCP locales)
    python node.py --id A --algo dijkstra

    # fase 2 (servidor XMPP)
    python node.py --id A --algo dijkstra --transport xmpp \
        --names configs/names-xmpp.txt --password secreto --server alumchat.lol
"""

import argparse
import asyncio
import logging
import sys

from core.config import ConfigError, NetworkConfig
from core.console import Console
from core.node import Node
from routing.dijkstra import Dijkstra
from transport.sockets import SocketTransport

# Al terminar un algoritmo, descomentar su import y su entrada en ALGORITMOS.
# No hay que tocar nada mas: ni el nodo, ni el transporte, ni el protocolo.
# from routing.flooding import Flooding
# from routing.lsr import LinkStateRouting
# from routing.dvr import DistanceVector

#: Registro de algoritmos disponibles.
#:
#: Un algoritmo es una clase en `routing/` que hereda de
#: `routing.common.base.RoutingAlgorithm`. Ver los archivos flooding.py,
#: lsr.py y dvr.py, que traen la guia de lo que hay que implementar.
ALGORITMOS = {
    "dijkstra": Dijkstra,
    # "flooding": Flooding,
    # "lsr": LinkStateRouting,
    # "dvr": DistanceVector,
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Nodo de la red de enrutamiento (Laboratorio 3 - Redes)"
    )
    parser.add_argument("--id", required=True, dest="node_id",
                        help="etiqueta de este nodo en los archivos de configuracion (A, B, ...)")
    parser.add_argument("--algo", required=True, choices=sorted(ALGORITMOS),
                        help="algoritmo de enrutamiento con el que se levanta la red")
    parser.add_argument("--topo", default="configs/topo-default.txt",
                        help="archivo de topologia (solo se lee la entrada propia)")
    parser.add_argument("--names", default="configs/names-sockets.txt",
                        help="archivo de asignacion de direcciones")
    parser.add_argument("--transport", default="sockets", choices=("sockets", "xmpp"),
                        help="medio de la red: sockets TCP (fase 1) o XMPP (fase 2)")
    parser.add_argument("--password", default=None, help="contrasena XMPP (solo --transport xmpp)")
    parser.add_argument("--server", default=None, help="host del servidor XMPP")
    parser.add_argument("--port", type=int, default=5222, help="puerto del servidor XMPP")
    parser.add_argument("--log-level", default="INFO",
                        choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--no-console", action="store_true",
                        help="no abrir la consola interactiva (util para pruebas automatizadas)")
    return parser.parse_args(argv)


def build_logger(node_id, level):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [{}] %(levelname)-7s %(message)s".format(node_id),
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(node_id)


async def run(args):
    log = build_logger(args.node_id, args.log_level)

    try:
        config = NetworkConfig(
            topo_path=args.topo,
            names_path=args.names,
            node_label=args.node_id,
            # Solo Dijkstra puro recibe la topologia completa como entrada.
            allow_full_topology=(args.algo == "dijkstra"),
        )
    except ConfigError as exc:
        log.error("%s", exc)
        return 1

    algorithm_factory = ALGORITMOS[args.algo]

    if args.transport == "xmpp":
        from transport.xmpp import XMPPTransport

        def transport_factory(node):
            return XMPPTransport(node, jid=node.address, password=args.password,
                                 server=args.server, port=args.port)
    else:
        transport_factory = SocketTransport

    node = Node(config, algorithm_factory, transport_factory, log)

    try:
        await node.start()
    except OSError as exc:
        log.error("no se pudo iniciar el transporte: %s", exc)
        return 1

    try:
        if args.no_console:
            await asyncio.Event().wait()
        else:
            await Console(node).run()
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()
        log.info("nodo detenido")
    return 0


def main(argv=None):
    args = parse_args(argv)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
