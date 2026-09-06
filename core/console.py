"""Consola interactiva del nodo.

Corre como una tarea mas del bucle de eventos, en paralelo al forwarding y al
routing. La lectura de stdin se delega a un hilo del executor para que sea
portable (en Windows no existe `loop.connect_read_pipe` sobre stdin).
"""

import asyncio
import sys

AYUDA = """
comandos disponibles
  send <destino> <texto>   envia un mensaje (destino: etiqueta 'B' o direccion completa)
  table                    tabla de enrutamiento actual
  neighbors                estado de los vecinos directos
  info                     estado interno del algoritmo (LSDB, vectores, rutas)
  stats                    contadores de paquetes de este nodo
  help                     esta ayuda
  quit                     termina el nodo
"""


class Console:
    def __init__(self, node):
        self.node = node
        self.running = True

    async def run(self):
        loop = asyncio.get_running_loop()
        print(AYUDA, flush=True)
        while self.running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except (EOFError, RuntimeError):
                return
            if not line:
                return
            try:
                await self._dispatch(line.strip())
            except Exception as exc:  # la consola nunca debe tumbar el nodo
                print("error: {}".format(exc), flush=True)

    async def _dispatch(self, line):
        if not line:
            return
        cmd, _, rest = line.partition(" ")
        cmd = cmd.lower()

        if cmd in ("quit", "exit", "salir"):
            self.running = False
        elif cmd in ("help", "ayuda", "?"):
            print(AYUDA, flush=True)
        elif cmd == "send":
            await self._send(rest)
        elif cmd in ("table", "tabla"):
            self._print_table()
        elif cmd in ("neighbors", "vecinos"):
            self._print_neighbors()
        elif cmd == "info":
            print(self.node.algorithm.describe() or "(sin estado interno)", flush=True)
        elif cmd == "stats":
            print(", ".join("{}={}".format(k, v) for k, v in self.node.stats.items()), flush=True)
        else:
            print("comando desconocido: {} (escriba 'help')".format(cmd), flush=True)

    async def _send(self, rest):
        destino, _, texto = rest.partition(" ")
        if not destino or not texto:
            print("uso: send <destino> <texto>", flush=True)
            return
        await self.node.send_message(self.node.config.resolve(destino), texto)

    def _print_table(self):
        rows = self.node.algorithm.table_rows()
        print("\ntabla de enrutamiento de {} ({})".format(self.node.label, self.node.proto), flush=True)
        if not rows:
            print("  (vacia: todavia no converge o no hay vecinos activos)\n", flush=True)
            return
        print("  {:<12} {:<14} {:>8}".format("destino", "siguiente", "costo"), flush=True)
        for dest, hop, cost in rows:
            print("  {:<12} {:<14} {:>8.1f}".format(dest, hop, cost), flush=True)
        print(flush=True)

    def _print_neighbors(self):
        print("\nvecinos de {}".format(self.node.label), flush=True)
        for neighbor in self.node.neighbors.all():
            rtt = "-" if neighbor.rtt is None else "{:.2f} ms".format(neighbor.rtt)
            print("  {:<8} {:<6} costo={:>7.1f}  rtt={}".format(
                neighbor.label, "up" if neighbor.alive else "DOWN", neighbor.cost, rtt), flush=True)
        print(flush=True)
