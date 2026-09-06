"""Carga de los archivos de configuracion (topo-*.txt y names-*.txt).

    topo-*.txt  -> {"type":"topo",  "config": {"A": ["B","C"], ...}}
    names-*.txt -> {"type":"names", "config": {"A":"foo@bar.com", ...}}

RESTRICCION DEL ENUNCIADO
-------------------------
Los archivos de configuracion solo pueden usarse para configurar el propio
nodo y descubrir sus vecinos. Por eso esta clase expone `my_neighbors()` y
`resolve()`, mientras que la topologia completa vive detras de
`full_topology()`, que lanza una excepcion salvo que el nodo se haya creado
con `allow_full_topology=True` (unicamente el modo Dijkstra puro, que segun
el enunciado si recibe la topologia como input).

Como identificador canonico de un nodo se usa su *direccion* (el valor del
archivo de nombres, p. ej. `foo@bar.com` o `127.0.0.1:5001`). Las letras
("A", "B", ...) son solo etiquetas para la interfaz de usuario y los logs.
"""

import json
import os


class ConfigError(Exception):
    pass


class TopologyAccessError(ConfigError):
    """Se intento leer la topologia completa desde un algoritmo dinamico."""


def _read_json_file(path, expected_type):
    if not os.path.exists(path):
        raise ConfigError("no existe el archivo de configuracion: {}".format(path))
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("type") != expected_type:
        raise ConfigError(
            "{}: se esperaba type='{}' y se encontro '{}'".format(path, expected_type, data.get("type"))
        )
    config = data.get("config")
    if not isinstance(config, dict):
        raise ConfigError("{}: falta el objeto 'config'".format(path))
    return config


def _normalize_links(raw):
    """Acepta ["B","C"] o {"B": 5, "C": 2} y devuelve {vecino: peso|None}."""
    if isinstance(raw, dict):
        return {str(k): float(v) for k, v in raw.items()}
    if isinstance(raw, (list, tuple)):
        return {str(k): None for k in raw}
    raise ConfigError("lista de vecinos invalida: {!r}".format(raw))


class NetworkConfig:
    def __init__(self, topo_path, names_path, node_label, allow_full_topology=False):
        self._topo = {k: _normalize_links(v) for k, v in _read_json_file(topo_path, "topo").items()}
        self._names = {k: str(v) for k, v in _read_json_file(names_path, "names").items()}
        self._allow_full = allow_full_topology

        if node_label not in self._names:
            raise ConfigError(
                "el nodo '{}' no aparece en el archivo de nombres {}".format(node_label, names_path)
            )
        if node_label not in self._topo:
            raise ConfigError(
                "el nodo '{}' no aparece en el archivo de topologia {}".format(node_label, topo_path)
            )

        self.label = node_label
        self.address = self._names[node_label]
        self._by_address = {addr: lbl for lbl, addr in self._names.items()}

    # ---- uso permitido: configurar mi nodo y descubrir mis vecinos ----

    def my_neighbors(self):
        """[(direccion, peso_configurado_o_None)] de MIS vecinos unicamente."""
        out = []
        for lbl, weight in self._topo[self.label].items():
            addr = self._names.get(lbl)
            if addr is None:
                raise ConfigError(
                    "el vecino '{}' de '{}' no tiene direccion asignada".format(lbl, self.label)
                )
            out.append((addr, weight))
        return out

    def address_of(self, label):
        return self._names.get(label)

    def label_of(self, address):
        """Etiqueta legible; si la direccion es desconocida se devuelve tal cual."""
        return self._by_address.get(address, address)

    def resolve(self, target):
        """Convierte lo que escribio el usuario ("B" o una direccion) en direccion."""
        if target in self._names:
            return self._names[target]
        return target

    def known_labels(self):
        return sorted(self._names.keys())

    # ---- uso restringido: solo Dijkstra puro ----

    def full_topology(self):
        """Grafo completo {direccion: {direccion_vecina: peso}}.

        Solo disponible para el algoritmo Dijkstra puro, que por definicion
        recibe la topologia como entrada. Cualquier otro algoritmo debe
        construir su vision de la red intercambiando paquetes.
        """
        if not self._allow_full:
            raise TopologyAccessError(
                "este algoritmo es dinamico: no puede leer la topologia completa "
                "del archivo de configuracion"
            )
        graph = {}
        for lbl, links in self._topo.items():
            addr = self._names.get(lbl)
            if addr is None:
                continue
            graph[addr] = {}
            for nb_lbl, weight in links.items():
                nb_addr = self._names.get(nb_lbl)
                if nb_addr is not None:
                    graph[addr][nb_addr] = 1.0 if weight is None else weight
        return graph
