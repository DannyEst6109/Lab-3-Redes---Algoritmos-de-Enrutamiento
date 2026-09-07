"""Prueba automatizada de la red completa sobre sockets (fase 1).

Levanta todos los nodos del archivo de topologia como procesos independientes,
espera a que el algoritmo converja, envia un mensaje desde el nodo origen al
nodo destino y verifica que haya sido entregado.

Uso:
    python scripts/test_network.py
    python scripts/test_network.py --topo configs/topo-weighted.txt --from A --to G
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

CONVERGENCIA = {"dijkstra": 8, "dvr": 20,
                "flooding": 6, "lsr": 20
                }


class NodoProceso:
    """Un nodo levantado como subproceso, con su salida capturada."""

    def __init__(self, label, algo, topo, names, log_level):
        self.label = label
        self.lineas = []
        self.proc = subprocess.Popen(
            [sys.executable, "-u", os.path.join(RAIZ, "node.py"),
             "--id", label, "--algo", algo, "--topo", topo, "--names", names,
             "--log-level", log_level],
            cwd=RAIZ,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self._hilo = threading.Thread(target=self._leer, daemon=True)
        self._hilo.start()

    def _leer(self):
        for linea in self.proc.stdout:
            self.lineas.append(linea.rstrip())

    def enviar(self, comando):
        self.proc.stdin.write(comando + "\n")
        self.proc.stdin.flush()

    def salida(self):
        return "\n".join(self.lineas)

    def detener(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write("quit\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        # Cerrar explicitamente evita el error del finalizador de stdin
        # cuando el proceso ya habia sido matado durante la prueba.
        for flujo in (self.proc.stdin, self.proc.stdout):
            try:
                flujo.close()
            except Exception:
                pass


def etiquetas(topo_path):
    with open(topo_path, encoding="utf-8") as fh:
        return sorted(json.load(fh)["config"].keys())


def escenario(algo, topo, names, origen, destino, espera, log_level):
    print("\n" + "=" * 68)
    print("ESCENARIO: algoritmo={}  {} -> {}".format(algo, origen, destino))
    print("=" * 68)

    nodos = {}
    try:
        for label in etiquetas(topo):
            nodos[label] = NodoProceso(label, algo, topo, names, log_level)
        print("[*] {} nodos levantados; esperando {}s a la convergencia...".format(
            len(nodos), espera))
        time.sleep(espera)

        nodos[origen].enviar("table")
        time.sleep(1.0)
        nodos[origen].enviar("send {} prueba-{}".format(destino, algo))
        time.sleep(5.0)

        recibido = "MENSAJE RECIBIDO" in nodos[destino].salida()

        print("\n--- tabla de enrutamiento de {} ---".format(origen))
        salida_origen = nodos[origen].salida()
        marca = "tabla de enrutamiento de"
        if marca in salida_origen:
            print(salida_origen[salida_origen.rindex(marca):][:800])

        if recibido:
            bloque = nodos[destino].salida()
            print("--- entrega en {} ---".format(destino))
            print(bloque[bloque.index("=== MENSAJE RECIBIDO ==="):][:400])

        print("\nRESULTADO: {}".format("OK - mensaje entregado" if recibido
                                       else "FALLO - el mensaje no llego"))
        return recibido
    finally:
        for nodo in nodos.values():
            nodo.detener()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algo", default="dijkstra", choices=sorted(CONVERGENCIA))
    parser.add_argument("--topo", default=os.path.join(RAIZ, "configs", "topo-default.txt"))
    parser.add_argument("--names", default=os.path.join(RAIZ, "configs", "names-sockets.txt"))
    parser.add_argument("--from", dest="origen", default="A")
    parser.add_argument("--to", dest="destino", default="G")
    parser.add_argument("--wait", type=float, default=None,
                        help="segundos de espera a la convergencia")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    algos = [args.algo]
    resultados = {}
    for algo in algos:
        espera = args.wait if args.wait is not None else CONVERGENCIA[algo]
        resultados[algo] = escenario(algo, args.topo, args.names,
                                     args.origen, args.destino, espera, args.log_level)

    print("\n" + "=" * 68)
    print("RESUMEN")
    for algo, ok in resultados.items():
        print("  {:<10} {}".format(algo, "OK" if ok else "FALLO"))
    return 0 if all(resultados.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
