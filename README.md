# Lab 3 Redes — Algoritmos de Enrutamiento

CC3067 Redes · Universidad del Valle de Guatemala

Red simulada de nodos independientes, donde cada nodo es un proceso que solo
conoce a sus vecinos y construye su tabla de enrutamiento intercambiando
paquetes. El medio de transporte es intercambiable: **sockets TCP** para el
desarrollo local (fase 1) y **XMPP** para la entrega oficial (fase 2).

## Contenido actual

Este repositorio contiene, por ahora, el **esqueleto compartido del nodo** y el
**algoritmo de Dijkstra**. Los demás algoritmos (Flooding, Link State Routing y
Distance Vector Routing) se integran sobre esta misma base — ver
[Cómo agregar un algoritmo](#cómo-agregar-un-algoritmo).

| Componente | Estado |
|---|---|
| Protocolo JSON, forwarding, descubrimiento de vecinos | Implementado |
| Transporte por sockets TCP (fase 1) | Implementado y probado |
| Transporte XMPP (fase 2) | Implementado, **pendiente de probar** contra el servidor |
| Dijkstra | Implementado y probado |
| Flooding, LSR, DVR | Pendientes |

---

## Requisitos e instalación

Python 3.9 o superior. Para la fase 1 (sockets) basta la biblioteca estándar.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

En Linux/macOS el activador es `source .venv/bin/activate`. `slixmpp` solo hace
falta para el transporte XMPP.

---

## Uso

### Pruebas automatizadas

Pruebas unitarias del algoritmo (rápidas, deterministas, no levantan red):

```bash
python scripts/test_dijkstra.py
```

Prueba de la red completa punta a punta: levanta todos los nodos de la
topología, espera la convergencia, envía un mensaje y verifica la entrega:

```bash
python scripts/test_network.py --topo configs/topo-weighted.txt
```

### Levantar un nodo a mano

Cada nodo se levanta en su propia terminal:

```bash
python node.py --id A --algo dijkstra --topo configs/topo-weighted.txt
```

Con la red arriba, la consola de cualquier nodo acepta:

| Comando | Efecto |
|---|---|
| `send <destino> <texto>` | Envía un mensaje (`send G hola`) |
| `table` | Tabla de enrutamiento actual |
| `neighbors` | Estado y costo de los enlaces directos |
| `info` | Estado interno del algoritmo y rutas completas |
| `stats` | Contadores de paquetes del nodo |
| `quit` | Termina el nodo |

### Fase 2 — XMPP

```bash
python node.py --id A --algo dijkstra --transport xmpp --names configs/names-xmpp.txt --password TU_CLAVE --server alumchat.lol
```

---

## Arquitectura

```
node.py                  punto de entrada: CLI, selección de algoritmo y transporte
core/
  packet.py              formato JSON del protocolo
  config.py              carga de topo-*.txt y names-*.txt, con la restricción de acceso
  neighbors.py           descubrimiento de vecinos y costo de enlace vía HELLO/ECHO
  node.py                proceso de FORWARDING y unión entre transporte y routing
  console.py             consola interactiva del nodo
routing/
  base.py                interfaz común de los algoritmos (proceso de ROUTING)
  dijkstra_core.py       algoritmo de Dijkstra puro, sin estado ni red
  dijkstra.py            modo de red estático basado en Dijkstra
transport/
  base.py                interfaz del medio
  sockets.py             transporte TCP (fase 1)
  xmpp.py                transporte XMPP (fase 2)
configs/                 archivos de topología y de nombres
scripts/                 pruebas automatizadas
```

Cada nodo corre **forwarding y routing en paralelo**, como pide el enunciado:
sobre un único bucle de `asyncio` conviven el servidor del transporte, el sondeo
periódico de vecinos, las tareas del algoritmo y la consola interactiva.

`dijkstra_core.py` está deliberadamente separado de `dijkstra.py`: el núcleo no
sabe nada de red ni mantiene estado, recibe un grafo y devuelve distancias y
primer salto. Eso permite que **Link State Routing lo reutilice tal cual** para
calcular sus rutas sobre la topología que reconstruye a partir de los LSPs.

### Cómo agregar un algoritmo

1. Crear el módulo en `routing/`, con una clase que herede de
   `routing.base.RoutingAlgorithm` e implemente al menos `route()`.
2. Registrarlo en el diccionario `ALGORITMOS` de `node.py`.

No hace falta tocar el nodo, el transporte ni el protocolo. Los ganchos
disponibles son `start()`, `stop()`, `on_neighbor_change()`, `handle_info()`,
`is_duplicate()`, `route()`, `table_rows()` y `describe()`; cada uno está
documentado en `routing/base.py`.

---

## Protocolo

Formato acordado en el enunciado, con cabeceras propias en el campo libre
`headers`:

```json
{
  "proto": "dijkstra",
  "type": "message",
  "from": "usuario_a@alumchat.lol",
  "to": "usuario_g@alumchat.lol",
  "ttl": 16,
  "headers": [{"mid": "a1b2c3"}, {"via": "usuario_b@alumchat.lol"}, {"hops": 2}, {"path": "A,B,C"}],
  "payload": "hola"
}
```

### Tipos de paquete

| Tipo | Uso |
|---|---|
| `hello` | Sondeo periódico a los vecinos; lleva la marca de tiempo `t0` |
| `echo` | Respuesta al sondeo; devuelve `t0` y permite medir el RTT |
| `info` | Información de routing (vectores de distancia, LSPs) |
| `message` | Datos de usuario |

### Cabeceras propias

| Cabecera | Significado |
|---|---|
| `mid` | Identificador del paquete, para deduplicar en algoritmos que inundan |
| `via` | Vecino que hizo el último salto |
| `t0` | Marca de tiempo del HELLO, para calcular el RTT |
| `hops` | Saltos recorridos, para diagnóstico |
| `path` | Traza de nodos recorridos, para verificar la ruta en las pruebas |

Todas son opcionales: si un nodo de otro grupo no las envía, la implementación
sigue funcionando.

---

## Costos de enlace

El costo de cada enlace es el **RTT medido** con los paquetes HELLO/ECHO,
suavizado con un promedio móvil exponencial. Si el archivo de topología declara
pesos explícitos (`{"A": {"B": 2}}`), se usan esos en su lugar, lo cual hace las
pruebas deterministas y reproducibles.

---

## Restricción sobre los archivos de configuración

El enunciado prohíbe usar los archivos de configuración para algo distinto de
configurar el propio nodo y descubrir sus vecinos. La restricción está
implementada, no solo documentada: `NetworkConfig.full_topology()` lanza
`TopologyAccessError` salvo que el nodo se construya con
`allow_full_topology=True`, cosa que `node.py` solo hace para Dijkstra puro —el
único algoritmo al que el enunciado le concede la topología como entrada—.

Los algoritmos dinámicos únicamente pueden llamar a `my_neighbors()`, que
devuelve la lista de vecinos propios. Toda su visión de la red deben
construirla con los paquetes que reciben.

---

## Resultados

Topología de prueba (`configs/topo-weighted.txt`):

```
enlaces (costo)      A-B 2    A-C 5    B-C 1    B-D 4
                     C-E 3    D-E 2    D-F 6    E-G 4    F-G 1
```

Tabla de enrutamiento calculada en el nodo A:

| Destino | Siguiente salto | Costo | Ruta |
|---|---|---|---|
| B | B | 2 | A→B |
| C | B | 3 | A→B→C |
| D | B | 6 | A→B→D |
| E | B | 6 | A→B→C→E |
| G | B | 10 | A→B→C→E→G |
| F | B | 11 | A→B→C→E→G→F |

El mensaje A → G viaja por `A,B,C,E,G`, la ruta óptima. Nótese que hacia F el
algoritmo prefiere rodear por G (costo 11) antes que usar el enlace directo
D-F (costo 12).

### Limitación conocida de Dijkstra

Es un algoritmo **estático**: recibe la topología como entrada y no intercambia
información con los demás nodos, así que no se entera de los cambios remotos de
la red. Lo único que un nodo puede observar por su cuenta es el estado de *sus
propios* enlaces (vía HELLO/ECHO), y ante la caída de un vecino directo
recalcula excluyendo ese enlace. La caída de un enlace lejano le es invisible.

Esa limitación no es un defecto de la implementación: es exactamente lo que
motiva la existencia de Link State Routing y Distance Vector Routing.
