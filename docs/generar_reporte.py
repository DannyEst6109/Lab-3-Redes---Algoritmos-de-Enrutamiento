"""Genera el reporte del laboratorio en PDF.

Se mantiene el reporte como codigo para que sea facil de versionar y de
regenerar cuando cada integrante complete su seccion.

    pip install reportlab
    python docs/generar_reporte.py

Produce `Reporte-Lab3.pdf` en la raiz del repositorio.
"""

import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "Reporte-Lab3.pdf")

FECHA = "Guatemala, 6 de septiembre de 2026"
INTEGRANTES = [
    "Daniel Estrada &ndash; 20853",
    "Melisa Mendizabal &ndash; 23778",
    "Renato Rojas &ndash; 23813",
    "Andre Pivaral &ndash; 23574",
]

# --------------------------------------------------------------------- estilos

_base = getSampleStyleSheet()

ST = {
    "portada_uvg": ParagraphStyle(
        "portada_uvg", parent=_base["Normal"], fontName="Times-Bold",
        fontSize=16, leading=22, alignment=TA_CENTER),
    "portada_sub": ParagraphStyle(
        "portada_sub", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=13, leading=20, alignment=TA_CENTER),
    "portada_titulo": ParagraphStyle(
        "portada_titulo", parent=_base["Normal"], fontName="Times-Bold",
        fontSize=17, leading=24, alignment=TA_CENTER),
    "portada_titulo2": ParagraphStyle(
        "portada_titulo2", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=13, leading=20, alignment=TA_CENTER),
    "portada_int": ParagraphStyle(
        "portada_int", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=12, leading=19, alignment=TA_CENTER),
    "h1": ParagraphStyle(
        "h1", parent=_base["Normal"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, spaceBefore=16, spaceAfter=8, keepWithNext=1),
    "h2": ParagraphStyle(
        "h2", parent=_base["Normal"], fontName="Helvetica-Bold",
        fontSize=11, leading=15, spaceBefore=12, spaceAfter=6, keepWithNext=1),
    "p": ParagraphStyle(
        "p", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=11, leading=15.5, alignment=TA_JUSTIFY, spaceAfter=8),
    "bullet": ParagraphStyle(
        "bullet", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=11, leading=15.5, alignment=TA_JUSTIFY,
        leftIndent=18, bulletIndent=6, spaceAfter=5),
    "code": ParagraphStyle(
        "code", parent=_base["Normal"], fontName="Courier",
        fontSize=8.5, leading=11.5, leftIndent=14, spaceBefore=4, spaceAfter=10,
        textColor=colors.HexColor("#1a1a1a"), keepWithNext=1),
    "caption": ParagraphStyle(
        "caption", parent=_base["Normal"], fontName="Times-Italic",
        fontSize=9.5, leading=13, alignment=TA_CENTER, spaceAfter=12),
    "nota": ParagraphStyle(
        "nota", parent=_base["Normal"], fontName="Times-Italic",
        fontSize=10, leading=14, alignment=TA_JUSTIFY,
        leftIndent=10, rightIndent=10, spaceBefore=4, spaceAfter=8,
        textColor=colors.HexColor("#444444")),
    "th": ParagraphStyle(
        "th", parent=_base["Normal"], fontName="Helvetica-Bold",
        fontSize=9.5, leading=12.5),
    "td": ParagraphStyle(
        "td", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=9.5, leading=12.5),
    "td_der": ParagraphStyle(
        "td_der", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=9.5, leading=12.5, alignment=2),
    "ref": ParagraphStyle(
        "ref", parent=_base["Normal"], fontName="Times-Roman",
        fontSize=10.5, leading=14,
        leftIndent=18, firstLineIndent=-18, spaceAfter=7),
}


# ------------------------------------------------------------------- atajos

def H1(texto):
    return Paragraph(texto, ST["h1"])


def H2(texto):
    return Paragraph(texto, ST["h2"])


def P(texto):
    return Paragraph(texto, ST["p"])


def LI(texto):
    return Paragraph(texto, ST["bullet"], bulletText="•")


def CODE(texto):
    lineas = [l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
              .replace(" ", "&nbsp;") for l in texto.strip("\n").split("\n")]
    return Paragraph("<br/>".join(lineas), ST["code"])


def CAP(texto):
    return Paragraph(texto, ST["caption"])


def NOTA(texto):
    return Paragraph(texto, ST["nota"])


def TABLA(datos, anchos=None, alineacion_der=()):
    # Las celdas se envuelven en Paragraph para que las entidades HTML
    # (acentos, flechas) se interpreten y para permitir el salto de linea.
    celdas = []
    for i, fila in enumerate(datos):
        nueva = []
        for j, celda in enumerate(fila):
            if i == 0:
                estilo_celda = ST["th"]
            else:
                estilo_celda = ST["td_der"] if j in alineacion_der else ST["td"]
            nueva.append(Paragraph(str(celda), estilo_celda))
        celdas.append(nueva)

    tabla = Table(celdas, colWidths=anchos, hAlign="CENTER", repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for col in alineacion_der:
        estilo.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))
    tabla.setStyle(TableStyle(estilo))
    return [tabla, Spacer(1, 10)]


def PENDIENTE(algoritmo, guia):
    """Bloque visible que marca una seccion por completar."""
    partes = [NOTA(
        "[SECCI&Oacute;N PENDIENTE &mdash; a completar por el integrante responsable de "
        "{}. Al terminarla, eliminar este recuadro.]".format(algoritmo))]
    partes.append(Paragraph("Contenido esperado en esta secci&oacute;n:", ST["p"]))
    for punto in guia:
        partes.append(LI(punto))
    partes.append(Spacer(1, 6))
    return partes


# -------------------------------------------------------------------- portada

def portada():
    e = [Spacer(1, 2.2 * cm),
         Paragraph("Universidad del Valle de Guatemala", ST["portada_uvg"]),
         Spacer(1, 0.5 * cm),
         Paragraph("Facultad de Ingenier&iacute;a", ST["portada_sub"]),
         Paragraph("CC3067 Redes &mdash; Semestre 2, 2026", ST["portada_sub"]),
         Spacer(1, 2.6 * cm),
         Paragraph("Laboratorio 3", ST["portada_titulo"]),
         Spacer(1, 0.3 * cm),
         Paragraph("Algoritmos de Enrutamiento", ST["portada_titulo"]),
         Spacer(1, 0.7 * cm),
         Paragraph("Implementaci&oacute;n y an&aacute;lisis de algoritmos de enrutamiento "
                   "sobre una red simulada de nodos independientes", ST["portada_titulo2"]),
         Spacer(1, 3.0 * cm),
         Paragraph("Integrantes:", ST["portada_int"]),
         Spacer(1, 0.35 * cm)]
    for nombre in INTEGRANTES:
        e.append(Paragraph(nombre, ST["portada_int"]))
    e += [Spacer(1, 3.0 * cm), Paragraph(FECHA, ST["portada_int"]), PageBreak()]
    return e


# ------------------------------------------------------------------ contenido

def seccion_practica():
    return [
        H1("1. Descripci&oacute;n de la pr&aacute;ctica"),
        P("Conocer hacia d&oacute;nde enviar un mensaje vuelve trivial el reenv&iacute;o: "
          "basta consultar el destino final en la tabla de enrutamiento y entregar el "
          "paquete al vecino que ofrece la mejor ruta. El problema real no es enrutar, "
          "sino <i>construir y mantener</i> esa tabla en una red que cambia: enlaces que "
          "caen, nodos que se incorporan y nodos que regresan tras una falla. Los "
          "algoritmos encargados de esa tarea son los algoritmos de enrutamiento, y son "
          "el objeto de esta pr&aacute;ctica."),
        P("El laboratorio consiste en implementar cuatro de esos algoritmos &mdash;Dijkstra, "
          "Flooding, Link State Routing y Distance Vector Routing&mdash; y probarlos sobre una "
          "red simulada. Cada nodo de la red es un proceso independiente que, al arrancar, "
          "conoce &uacute;nicamente la identidad de sus vecinos inmediatos. Toda su visi&oacute;n "
          "del resto de la red debe construirla intercambiando mensajes, tal como lo hace "
          "un router real, que ve los enlaces conectados a &eacute;l pero desconoce la "
          "topolog&iacute;a global."),
        P("La pr&aacute;ctica se divide en dos fases. La primera utiliza sockets TCP sobre la "
          "m&aacute;quina local como medio de comunicaci&oacute;n, lo que permite concentrarse en los "
          "algoritmos sin depender de infraestructura externa. La segunda escala esa misma "
          "implementaci&oacute;n a un servidor XMPP, donde cada nodo corresponde a un usuario de "
          "la red y que constituye la entrega oficial. La l&oacute;gica de enrutamiento es "
          "id&eacute;ntica en ambas fases; lo &uacute;nico que cambia es el medio."),
        H2("1.1 Objetivos"),
        LI("Conocer los algoritmos de enrutamiento utilizados en las implementaciones "
           "actuales de Internet."),
        LI("Comprender c&oacute;mo funcionan las tablas de enrutamiento."),
        LI("Implementar los algoritmos y probarlos en una red simulada sobre un protocolo "
           "de capa superior."),
        LI("Analizar el funcionamiento y las limitaciones de cada algoritmo."),
        Spacer(1, 4),
        H2("1.2 Distribuci&oacute;n del trabajo"),
        P("El enunciado establece la implementaci&oacute;n de un algoritmo por integrante. La "
          "asignaci&oacute;n fue la siguiente:"),
    ] + TABLA([
        ["#", "Algoritmo", "Archivo", "Integrante"],
        ["1", "Dijkstra", "routing/dijkstra.py", "Daniel Estrada"],
        ["2", "Flooding", "routing/flooding.py", "(por asignar)"],
        ["3", "Link State Routing", "routing/lsr.py", "(por asignar)"],
        ["4", "Distance Vector Routing", "routing/dvr.py", "(por asignar)"],
    ], anchos=[1.0 * cm, 5.2 * cm, 4.8 * cm, 4.6 * cm])


def seccion_diseno():
    return [
        H1("2. Dise&ntilde;o general de la implementaci&oacute;n"),
        P("Los cuatro algoritmos comparten la misma infraestructura: el formato de los "
          "paquetes, el descubrimiento de vecinos, el proceso de reenv&iacute;o y el medio de "
          "transporte. Solo difieren en c&oacute;mo deciden el siguiente salto. El dise&ntilde;o "
          "aprovecha esa separaci&oacute;n: existe un &uacute;nico tipo de nodo con dos ejes "
          "intercambiables, el algoritmo de enrutamiento y el medio de transporte."),
        CODE("""
node.py                  punto de entrada: CLI, seleccion de algoritmo y transporte
core/
  packet.py              formato JSON del protocolo
  config.py              carga de topo-*.txt y names-*.txt, con la restriccion de acceso
  neighbors.py           descubrimiento de vecinos y costo de enlace via HELLO/ECHO
  node.py                proceso de FORWARDING
  console.py             consola interactiva del nodo
routing/                 LOS ALGORITMOS: un archivo por algoritmo
  dijkstra.py  flooding.py  lsr.py  dvr.py
  common/                infraestructura compartida
    base.py                interfaz comun que todos implementan
    shortest_path.py       Dijkstra puro sobre un grafo (lo usan dijkstra y lsr)
    seen_cache.py          deduplicacion de paquetes (la usan flooding y lsr)
transport/
  base.py  sockets.py (fase 1)  xmpp.py (fase 2)
configs/                 archivos de topologia y de nombres
scripts/                 pruebas automatizadas
"""),
        CAP("Figura 1. Estructura del proyecto."),
        P("El enunciado exige adem&aacute;s que Dijkstra y Flooding sean reutilizables desde "
          "Link State Routing sin dejar de funcionar como algoritmos de red aut&oacute;nomos. "
          "Por eso el n&uacute;cleo de Dijkstra vive en <font face='Courier' size='9'>"
          "routing/common/shortest_path.py</font>, sin estado y sin conocimiento de la red: "
          "recibe un grafo y un origen, y devuelve distancias y primer salto. Lo mismo "
          "aplica a la deduplicaci&oacute;n de paquetes inundados, que Flooding y la difusi&oacute;n "
          "de LSPs de LSR comparten a trav&eacute;s de "
          "<font face='Courier' size='9'>common/seen_cache.py</font>."),
        H2("2.1 Modelo de nodo: forwarding y routing en paralelo"),
        P("Cada nodo ejecuta dos servicios simult&aacute;neos, seg&uacute;n exige el enunciado. El "
          "<b>forwarding</b> es reactivo: recibe un paquete, determina si es para el propio "
          "nodo &mdash;en cuyo caso lo entrega al usuario&mdash; o consulta la tabla y lo reenv&iacute;a. "
          "Nunca calcula rutas. El <b>routing</b> trabaja en segundo plano: emite anuncios "
          "peri&oacute;dicos, procesa los de los dem&aacute;s y recalcula la tabla. Nunca manipula los "
          "mensajes de usuario. El forwarding <i>lee</i> la tabla y el routing la "
          "<i>escribe</i>; ese es todo el contrato entre ambos."),
        P("La concurrencia se resuelve con <font face='Courier' size='9'>asyncio</font>. "
          "Sobre un &uacute;nico bucle de eventos conviven, como tareas independientes, el "
          "servidor del transporte, el sondeo peri&oacute;dico de vecinos, las tareas del "
          "algoritmo y la consola interactiva. Esto evita las condiciones de carrera "
          "propias de los hilos sin renunciar al paralelismo l&oacute;gico que pide la "
          "pr&aacute;ctica."),
        H2("2.2 Protocolo de mensajes"),
        P("Se respeta el formato JSON definido en el enunciado, com&uacute;n a todos los grupos "
          "para permitir la interoperabilidad:"),
        CODE("""
{
  "proto"  : "dijkstra|flooding|lsr|dvr",
  "type"   : "message|echo|info|hello",
  "from"   : "usuario_a@alumchat.lol",
  "to"     : "usuario_g@alumchat.lol",
  "ttl"    : 16,
  "headers": [{"mid":"a1b2c3"}, {"via":"usuario_b@alumchat.lol"}, {"hops":2}],
  "payload": "contenido segun el tipo de paquete"
}
"""),
        P("Se emplean los cuatro tipos de paquete sugeridos. Los paquetes "
          "<font face='Courier' size='9'>hello</font> y "
          "<font face='Courier' size='9'>echo</font> sirven al descubrimiento de vecinos y "
          "a la medici&oacute;n de distancias; <font face='Courier' size='9'>info</font> "
          "transporta la informaci&oacute;n de enrutamiento (vectores de distancia o LSPs) y "
          "<font face='Courier' size='9'>message</font> lleva los datos de usuario."),
        P("Sobre el campo libre <font face='Courier' size='9'>headers</font> se definieron "
          "cabeceras propias. Todas son opcionales: si un nodo de otro grupo no las env&iacute;a, "
          "la implementaci&oacute;n contin&uacute;a operando y solo pierde la optimizaci&oacute;n asociada."),
    ] + TABLA([
        ["Cabecera", "Prop&oacute;sito"],
        ["mid", "Identificador &uacute;nico del paquete, base de la deduplicaci&oacute;n en Flooding"],
        ["via", "Vecino que realiz&oacute; el &uacute;ltimo salto; habilita el split horizon en DVR"],
        ["t0", "Marca de tiempo del HELLO, empleada para calcular el RTT"],
        ["hops", "Saltos recorridos por el paquete, con fines de diagn&oacute;stico"],
        ["path", "Traza de nodos recorridos, usada para verificar la ruta en las pruebas"],
    ], anchos=[2.6 * cm, 12.4 * cm]) + [
        H2("2.3 Descubrimiento de vecinos y costo de enlace"),
        P("Un nodo conoce por configuraci&oacute;n la lista de sus vecinos, pero no si est&aacute;n "
          "operativos ni a qu&eacute; distancia se encuentran. Para resolverlo, cada nodo env&iacute;a "
          "peri&oacute;dicamente un paquete HELLO a cada vecino con una marca de tiempo; el vecino "
          "responde con un ECHO que devuelve esa marca, y el emisor obtiene as&iacute; el tiempo "
          "de ida y vuelta. El costo del enlace es ese RTT suavizado con un promedio m&oacute;vil "
          "exponencial, lo que amortigua las variaciones puntuales de la m&aacute;quina."),
        P("Este mecanismo es adem&aacute;s el detector de fallas del sistema: un vecino que deja "
          "de responder durante un intervalo determinado se marca como ca&iacute;do y se notifica "
          "al algoritmo de enrutamiento, que es lo que dispara la reconvergencia. "
          "Opcionalmente, si el archivo de topolog&iacute;a declara pesos expl&iacute;citos, se utilizan "
          "esos valores en lugar del RTT, lo que hace las pruebas deterministas y "
          "reproducibles."),
        H2("2.4 Restricci&oacute;n sobre los archivos de configuraci&oacute;n"),
        P("El enunciado proh&iacute;be emplear los archivos de configuraci&oacute;n para algo distinto "
          "de configurar el propio nodo y descubrir sus vecinos; en particular, proh&iacute;be "
          "leer la topolog&iacute;a completa y resolver las rutas de forma est&aacute;tica. La "
          "restricci&oacute;n se implement&oacute; en el c&oacute;digo y no solo en la documentaci&oacute;n: el "
          "m&eacute;todo <font face='Courier' size='9'>NetworkConfig.full_topology()</font> lanza "
          "la excepci&oacute;n <font face='Courier' size='9'>TopologyAccessError</font> salvo que "
          "el nodo se haya construido expl&iacute;citamente con permiso, cosa que ocurre "
          "&uacute;nicamente cuando el algoritmo seleccionado es Dijkstra puro, el &uacute;nico al que el "
          "enunciado concede la topolog&iacute;a como entrada."),
        P("Los algoritmos din&aacute;micos solo pueden invocar "
          "<font face='Courier' size='9'>my_neighbors()</font>, que devuelve exclusivamente "
          "la lista de vecinos propios. De este modo la restricci&oacute;n deja de depender de la "
          "disciplina del programador y se convierte en una garant&iacute;a verificable."),
    ]


def seccion_algoritmos():
    e = [
        H1("3. Descripci&oacute;n de los algoritmos y su implementaci&oacute;n"),
        P("Los cuatro algoritmos se distinguen por la informaci&oacute;n de la que disponen, y "
          "esa diferencia determina por completo su comportamiento:"),
    ]
    e += TABLA([
        ["Algoritmo", "Informaci&oacute;n de entrada", "Naturaleza"],
        ["Dijkstra", "Topolog&iacute;a completa", "Est&aacute;tico"],
        ["Flooding", "&Uacute;nicamente sus vecinos", "Din&aacute;mico, sin tabla"],
        ["Link State Routing", "LSPs de todos los nodos", "Din&aacute;mico, visi&oacute;n global"],
        ["Distance Vector", "Tablas de sus vecinos", "Din&aacute;mico, visi&oacute;n local"],
    ], anchos=[4.4 * cm, 6.2 * cm, 4.4 * cm])

    # ---- 3.1 Dijkstra (implementado) ----
    e += [
        H2("3.1 Dijkstra"),
        P("Dijkstra resuelve el problema de caminos m&iacute;nimos desde un origen en un grafo "
          "con pesos no negativos. Parte de una distancia nula al origen e infinita al "
          "resto, y de forma iterativa extrae el nodo no visitado de menor distancia "
          "conocida y relaja sus aristas: si llegar a un vecino a trav&eacute;s del nodo actual "
          "resulta m&aacute;s barato que la mejor distancia registrada hasta ese vecino, la "
          "distancia se actualiza. El invariante que sostiene su correcci&oacute;n es que, al "
          "extraer un nodo, su distancia ya es definitiva, lo cual solo se cumple si "
          "ning&uacute;n peso es negativo."),
        P("La implementaci&oacute;n emplea un heap binario con borrado perezoso: en lugar de "
          "actualizar la prioridad de una entrada existente se inserta una nueva y las "
          "obsoletas se descartan al extraerlas, comprobando si el nodo ya fue visitado. "
          "El costo resultante es O((V + E) log V), donde V es el n&uacute;mero de nodos y E el "
          "de enlaces."),
        P("Una tabla de enrutamiento, sin embargo, no necesita la ruta completa hacia cada "
          "destino, sino &uacute;nicamente el <i>primer salto</i>. En lugar de reconstruir cada "
          "camino al final, el primer salto se propaga durante la relajaci&oacute;n: los vecinos "
          "directos del origen son su propio primer salto, y cualquier otro nodo hereda el "
          "primer salto de su predecesor. As&iacute; la tabla queda construida al terminar el "
          "recorrido, sin recorridos adicionales."),
        CODE("""
def shortest_paths(graph, source):
    dist = {source: 0.0}; first_hop = {}; previous = {}
    visited = set(); heap = [(0.0, source)]

    while heap:
        d, node = heapq.heappop(heap)
        if node in visited:          # entrada obsoleta (borrado perezoso)
            continue
        visited.add(node)

        for neighbor, weight in (graph.get(node) or {}).items():
            if neighbor in visited or weight is None or weight < 0:
                continue
            candidate = d + weight
            if candidate < dist.get(neighbor, INF):
                dist[neighbor] = candidate
                previous[neighbor] = node
                # el primer salto se hereda del predecesor
                first_hop[neighbor] = neighbor if node == source else first_hop[node]
                heapq.heappush(heap, (candidate, neighbor))

    dist.pop(source, None)
    return dist, first_hop, previous
"""),
        CAP("Figura 2. N&uacute;cleo de Dijkstra (routing/common/shortest_path.py)."),
        P("El m&oacute;dulo se mantiene deliberadamente libre de red y de estado. Esa decisi&oacute;n "
          "es la que permite que Link State Routing lo reutilice sin modificaciones para "
          "calcular sus rutas sobre la topolog&iacute;a que reconstruye a partir de los LSPs, "
          "que es exactamente lo que solicita el enunciado."),
        P("Sobre ese n&uacute;cleo, <font face='Courier' size='9'>routing/dijkstra.py</font> "
          "implementa el modo de red: obtiene la topolog&iacute;a de la configuraci&oacute;n, calcula "
          "la tabla al arrancar y responde a las consultas del proceso de forwarding. "
          "Puesto que no intercambia informaci&oacute;n con los dem&aacute;s nodos, es un algoritmo "
          "est&aacute;tico y no puede enterarse de los cambios remotos de la red. Lo &uacute;nico que "
          "un nodo puede observar por s&iacute; mismo es el estado de sus propios enlaces, "
          "mediante HELLO/ECHO; ante la ca&iacute;da de un vecino directo la implementaci&oacute;n "
          "recalcula excluyendo ese enlace, que es todo lo que el algoritmo permite hacer "
          "sin violar sus premisas."),
    ]

    # ---- 3.2 Flooding ----
    e += [H2("3.2 Flooding")]
    e += PENDIENTE("Flooding", [
        "Descripci&oacute;n del algoritmo: el nodo reenv&iacute;a todo paquete que no es para &eacute;l por "
        "todos sus enlaces activos salvo aquel por el que lleg&oacute;; no construye tabla.",
        "Mecanismo de deduplicaci&oacute;n por identificador de paquete y por qu&eacute; es "
        "indispensable: sin &eacute;l, en una topolog&iacute;a con ciclos el n&uacute;mero de copias crece "
        "exponencialmente.",
        "Papel del TTL como l&iacute;mite superior del recorrido y red de seguridad ante el "
        "reinicio de un nodo.",
        "Fragmento de c&oacute;digo representativo de <font face='Courier' size='9'>route()</font> "
        "y de <font face='Courier' size='9'>is_duplicate()</font>.",
        "Optimizaciones aplicadas, si las hubo (por ejemplo, entrega directa cuando el "
        "destino es un vecino inmediato).",
    ])

    # ---- 3.3 LSR ----
    e += [H2("3.3 Link State Routing")]
    e += PENDIENTE("Link State Routing", [
        "Descripci&oacute;n en dos etapas: difusi&oacute;n de LSPs por inundaci&oacute;n y c&aacute;lculo local de "
        "rutas con Dijkstra sobre la topolog&iacute;a reconstruida.",
        "Estructura del LSP empleada (origen, n&uacute;mero de secuencia y estado de los enlaces "
        "propios) y estructura de la base de datos de estado de enlace (LSDB).",
        "Control de la inundaci&oacute;n mediante n&uacute;meros de secuencia: por qu&eacute; es lo que hace "
        "que la difusi&oacute;n termine en topolog&iacute;as con ciclos.",
        "Envejecimiento de los LSPs y su efecto: retirar de la topolog&iacute;a a los nodos que "
        "dejan de emitir.",
        "Reutilizaci&oacute;n expl&iacute;cita de Flooding y de "
        "<font face='Courier' size='9'>common/shortest_path.py</font>, seg&uacute;n exige el "
        "enunciado.",
        "Tratamiento de los enlaces declarados por un solo extremo durante la "
        "convergencia, si se implement&oacute; verificaci&oacute;n de bidireccionalidad.",
    ])

    # ---- 3.4 DVR ----
    e += [H2("3.4 Distance Vector Routing")]
    e += PENDIENTE("Distance Vector Routing", [
        "Descripci&oacute;n del algoritmo como Bellman-Ford distribuido y planteamiento de la "
        "ecuaci&oacute;n D(x,y) = min<sub>v</sub> [ c(x,v) + D(v,y) ].",
        "Formato del vector anunciado y periodicidad de los anuncios.",
        "Problema de count to infinity y medidas adoptadas: split horizon con poison "
        "reverse y l&iacute;mite de saltos.",
        "Justificaci&oacute;n de que el l&iacute;mite sea de saltos y no de costo: el costo de enlace "
        "es el RTT en milisegundos, de modo que un umbral sobre el costo declarar&iacute;a "
        "inalcanzables rutas v&aacute;lidas.",
        "Caducidad de los vectores de vecinos que dejan de anunciar.",
        "Actualizaciones disparadas (triggered updates) y su efecto sobre el tiempo de "
        "convergencia.",
    ])
    return e


def seccion_resultados():
    e = [
        H1("4. Resultados"),
        H2("4.1 Escenario de prueba"),
        P("Las pruebas se realizaron sobre la fase 1 (sockets TCP en la m&aacute;quina local), "
          "levantando siete nodos como procesos independientes. Se utiliz&oacute; una topolog&iacute;a "
          "con pesos expl&iacute;citos para obtener resultados deterministas y reproducibles, "
          "verificables a mano:"),
        CODE("""
enlaces (costo)    A-B 2    A-C 5    B-C 1    B-D 4
                   C-E 3    D-E 2    D-F 6    E-G 4    F-G 1
"""),
        CAP("Figura 3. Topolog&iacute;a de prueba (configs/topo-weighted.txt)."),
        P("El procedimiento automatizado levanta los siete nodos, espera la convergencia, "
          "env&iacute;a un mensaje del nodo A al nodo G y verifica tanto la entrega como la ruta "
          "seguida, que viaja registrada en la cabecera "
          "<font face='Courier' size='9'>path</font>."),
        H2("4.2 Convergencia y rutas obtenidas"),
        P("La tabla de enrutamiento calculada por el nodo A fue la siguiente. La ruta "
          "&oacute;ptima hacia G es A&rarr;B&rarr;C&rarr;E&rarr;G con costo 10, y la implementaci&oacute;n la "
          "reproduce exactamente:"),
    ]
    e += TABLA([
        ["Destino", "Siguiente salto", "Costo", "Ruta completa"],
        ["B", "B", "2", "A &rarr; B"],
        ["C", "B", "3", "A &rarr; B &rarr; C"],
        ["D", "B", "6", "A &rarr; B &rarr; D"],
        ["E", "B", "6", "A &rarr; B &rarr; C &rarr; E"],
        ["G", "B", "10", "A &rarr; B &rarr; C &rarr; E &rarr; G"],
        ["F", "B", "11", "A &rarr; B &rarr; C &rarr; E &rarr; G &rarr; F"],
    ], anchos=[2.2 * cm, 3.2 * cm, 1.8 * cm, 7.8 * cm], alineacion_der=(2,))
    e += [
        CAP("Tabla 1. Tabla de enrutamiento del nodo A con el algoritmo Dijkstra."),
        P("Merece atenci&oacute;n el destino F. Existe un camino m&aacute;s corto en n&uacute;mero de saltos "
          "(A&rarr;B&rarr;D&rarr;F, tres saltos) pero m&aacute;s caro (2+4+6 = 12), frente al que "
          "efectivamente se elige, de cinco saltos y costo 11. El algoritmo optimiza costo "
          "acumulado y no cantidad de saltos, y el resultado lo confirma."),
        P("El mensaje enviado de A hacia G fue entregado por la ruta "
          "A,B,C,E,G, coincidente con la ruta &oacute;ptima calculada:"),
        CODE("""
=== MENSAJE RECIBIDO ===
  de     : A
  saltos : 4
  ruta   : A,B,C,E,G
  texto  : prueba-dijkstra

RESULTADO: OK - mensaje entregado
"""),
        CAP("Figura 4. Salida del nodo G al recibir el mensaje."),
        H2("4.3 Verificaci&oacute;n unitaria del algoritmo"),
        P("Adem&aacute;s de la prueba de red, el n&uacute;cleo de Dijkstra se verific&oacute; de forma aislada "
          "contra grafos de respuesta conocida, incluyendo los casos borde que suelen "
          "romper una implementaci&oacute;n. Las seis familias de prueba, con dieciseis "
          "verificaciones en total, se ejecutan sin levantar la red y todas resultaron "
          "correctas:"),
    ]
    e += TABLA([
        ["Caso de prueba", "Resultado"],
        ["Distancias y primer salto en la topolog&iacute;a con pesos", "Correcto"],
        ["Ruta &oacute;ptima evitando el enlace caro D-F", "Correcto"],
        ["Topolog&iacute;a sin el nodo C: el costo A&rarr;G sube de 10 a 12", "Correcto"],
        ["Grafo desconectado: los nodos inalcanzables no entran a la tabla", "Correcto"],
        ["Nodo sin vecinos activos: tabla vac&iacute;a, sin errores", "Correcto"],
        ["Empate de costos: primer salto estable y v&aacute;lido", "Correcto"],
        ["Vecino directo: el primer salto es el propio destino", "Correcto"],
    ], anchos=[10.6 * cm, 4.4 * cm])
    e += [
        CAP("Tabla 2. Verificaci&oacute;n unitaria de routing/common/shortest_path.py."),
        H2("4.4 Resultados de los dem&aacute;s algoritmos"),
    ]
    e += PENDIENTE("Flooding, Link State Routing y Distance Vector Routing", [
        "Tabla de enrutamiento obtenida en el nodo A con cada algoritmo, comparada con la "
        "de Dijkstra centralizado de la Tabla 1: una implementaci&oacute;n correcta de LSR y de "
        "DVR debe converger exactamente a los mismos valores.",
        "Ruta seguida por el mensaje A&rarr;G en cada caso y n&uacute;mero de saltos.",
        "Tiempo aproximado de convergencia observado en cada algoritmo.",
        "Prueba de robustez: ruta antes de la ca&iacute;da de un nodo intermedio, ruta despu&eacute;s "
        "de la reconvergencia y, si aplica, ruta tras la reincorporaci&oacute;n del nodo.",
        "En Flooding, cantidad de paquetes duplicados descartados, que ilustra el costo "
        "en tr&aacute;fico del algoritmo.",
    ])
    return e


def seccion_discusion():
    return [
        H1("5. Discusi&oacute;n"),
        P("El resultado m&aacute;s ilustrativo de la pr&aacute;ctica no es que los algoritmos funcionen, "
          "sino <i>c&oacute;mo</i> llegan al mismo lugar por caminos opuestos. Dijkstra dispone del "
          "mapa completo y calcula la respuesta de una sola vez. Link State Routing no lo "
          "tiene, pero lo reconstruye: cada nodo publica el estado de sus propios enlaces, "
          "la informaci&oacute;n se inunda por la red y al final todos poseen el mismo mapa, "
          "sobre el cual ejecutan el mismo Dijkstra. Distance Vector nunca llega a ver el "
          "mapa; sus nodos solo intercambian distancias y aun as&iacute;, si la implementaci&oacute;n "
          "es correcta, convergen a las mismas rutas. Que tres estrategias tan distintas "
          "produzcan tablas id&eacute;nticas es la mejor evidencia de correcci&oacute;n disponible, y "
          "por eso la Tabla 1 sirve de referencia para validar los otros algoritmos."),
        P("La limitaci&oacute;n de Dijkstra qued&oacute; expuesta con claridad en las pruebas. Al "
          "recibir la topolog&iacute;a como entrada y no intercambiar informaci&oacute;n con los dem&aacute;s "
          "nodos, un cambio remoto de la red le resulta invisible: si un enlace lejano "
          "desaparece, el nodo sigue calculando rutas sobre una topolog&iacute;a que ya no "
          "existe y los paquetes se pierden en el camino. Solo puede reaccionar a la "
          "ca&iacute;da de sus propios vecinos, que es lo &uacute;nico que percibe directamente. Esta "
          "limitaci&oacute;n no es un defecto de la implementaci&oacute;n sino la definici&oacute;n misma de "
          "un algoritmo est&aacute;tico, y es exactamente lo que justifica la existencia de LSR "
          "y de DVR."),
        P("La restricci&oacute;n del enunciado sobre los archivos de configuraci&oacute;n result&oacute; ser, "
          "en la pr&aacute;ctica, la decisi&oacute;n de dise&ntilde;o m&aacute;s importante. Es tentador leer la "
          "topolog&iacute;a completa y resolver todo de forma est&aacute;tica, porque el resultado "
          "inmediato parece correcto; pero hacerlo convierte a los cuatro algoritmos en "
          "el mismo algoritmo y elimina toda capacidad de adaptaci&oacute;n. Implementar la "
          "restricci&oacute;n como una excepci&oacute;n en el c&oacute;digo, y no como una nota en la "
          "documentaci&oacute;n, obliga a que cada algoritmo construya su visi&oacute;n de la red por "
          "los medios que le corresponden."),
        P("La elecci&oacute;n del RTT medido como costo de enlace, en lugar de un peso "
          "arbitrario, acerca la simulaci&oacute;n a una red real, pero introduce una dificultad "
          "que conviene se&ntilde;alar: los costos dejan de ser n&uacute;meros peque&ntilde;os y pasan a ser "
          "milisegundos, con valores que var&iacute;an entre ejecuciones. Cualquier umbral "
          "constante heredado de la literatura &mdash;el infinito igual a 16 de RIP es el "
          "ejemplo t&iacute;pico&mdash; deja de tener sentido, porque un enlace perfectamente sano "
          "puede costar 20. Es un error silencioso: la tabla queda vac&iacute;a sin que ninguna "
          "excepci&oacute;n lo indique. Por eso la topolog&iacute;a con pesos expl&iacute;citos result&oacute; "
          "indispensable para las pruebas: separa los errores del algoritmo del ruido de "
          "la medici&oacute;n."),
        P("Finalmente, la separaci&oacute;n entre el n&uacute;cleo del algoritmo y su modo de red "
          "demostr&oacute; su valor m&aacute;s all&aacute; de la limpieza del c&oacute;digo. Al mantener "
          "<font face='Courier' size='9'>shortest_path.py</font> sin estado y sin "
          "conocimiento de la red, fue posible verificarlo de forma unitaria contra "
          "respuestas calculadas a mano, sin levantar siete procesos ni esperar la "
          "convergencia. Depurar un algoritmo distribuido observando &uacute;nicamente su "
          "comportamiento agregado es considerablemente m&aacute;s dif&iacute;cil que verificar por "
          "separado la pieza determinista."),
    ]


def seccion_conclusiones():
    return [
        H1("6. Conclusiones"),
        LI("El problema central del enrutamiento no es reenviar paquetes, sino construir "
           "y mantener la tabla que hace posible ese reenv&iacute;o. Los cuatro algoritmos "
           "resuelven la misma pregunta con informaci&oacute;n distinta, y la cantidad de "
           "informaci&oacute;n de la que disponen determina por completo sus capacidades y sus "
           "limitaciones."),
        LI("Dijkstra produce rutas &oacute;ptimas de forma inmediata cuando la topolog&iacute;a es "
           "conocida y estable, pero al no intercambiar informaci&oacute;n con los dem&aacute;s nodos "
           "no puede adaptarse a los cambios remotos de la red. Su valor real en esta "
           "pr&aacute;ctica es doble: sirve como referencia de correcci&oacute;n para los algoritmos "
           "din&aacute;micos y constituye el motor de c&aacute;lculo de Link State Routing."),
        LI("La modularidad exigida por el enunciado no es un requisito est&eacute;tico. Mantener "
           "el n&uacute;cleo de Dijkstra libre de estado y de red permiti&oacute; reutilizarlo sin "
           "modificaciones y verificarlo de forma aislada, lo que redujo notablemente la "
           "dificultad de depuraci&oacute;n frente a la alternativa de probar todo el sistema "
           "distribuido en conjunto."),
        LI("Implementar en el c&oacute;digo la restricci&oacute;n de acceso a la topolog&iacute;a, mediante "
           "una excepci&oacute;n en lugar de una advertencia en la documentaci&oacute;n, result&oacute; ser "
           "una decisi&oacute;n acertada: convierte una regla del enunciado en una garant&iacute;a "
           "verificable y evita el atajo que anular&iacute;a el prop&oacute;sito del laboratorio."),
        LI("Separar la l&oacute;gica de enrutamiento del medio de transporte permiti&oacute; desarrollar "
           "y probar por completo la primera fase sobre sockets TCP, dejando el paso al "
           "servidor XMPP como un cambio de una sola clase, sin tocar los algoritmos."),
        H1("7. Comentarios"),
        P("El aspecto que mayor coordinaci&oacute;n exige de cara a la prueba en clase no es "
          "algor&iacute;tmico sino de acuerdo entre grupos. El enunciado fija la estructura del "
          "paquete, pero deja libre el contenido del campo "
          "<font face='Courier' size='9'>payload</font> de los paquetes de tipo "
          "<font face='Courier' size='9'>info</font>, que es justamente donde viajan los "
          "vectores de distancia y los LSPs. Si cada grupo define ese contenido por su "
          "cuenta, Flooding funcionar&aacute; entre implementaciones distintas &mdash;no necesita "
          "acuerdo alguno&mdash; pero LSR y DVR se ignorar&aacute;n mutuamente, descartando como "
          "malformada la informaci&oacute;n del otro. Conviene fijar ese formato antes de la "
          "sesi&oacute;n de pruebas."),
        P("Como medida preventiva, la implementaci&oacute;n trata todas las cabeceras propias "
          "como opcionales: si un nodo de otro grupo no las env&iacute;a, el algoritmo contin&uacute;a "
          "operando y &uacute;nicamente pierde la optimizaci&oacute;n asociada, sin romper la "
          "interoperabilidad."),
    ]


def seccion_referencias():
    return [
        H1("8. Referencias"),
        Paragraph("Kurose, J. F., &amp; Ross, K. W. (2021). <i>Computer Networking: A "
                  "Top-Down Approach</i> (8.<sup>a</sup> ed.). Pearson.", ST["ref"]),
        Paragraph("Tanenbaum, A. S., &amp; Wetherall, D. J. (2011). <i>Computer "
                  "Networks</i> (5.<sup>a</sup> ed.). Prentice Hall.", ST["ref"]),
        Paragraph("Dijkstra, E. W. (1959). A note on two problems in connexion with "
                  "graphs. <i>Numerische Mathematik, 1</i>(1), 269&ndash;271.", ST["ref"]),
        Paragraph("Malkin, G. (1998). <i>RIP Version 2</i> (RFC 2453). Internet "
                  "Engineering Task Force. https://www.rfc-editor.org/rfc/rfc2453",
                  ST["ref"]),
        Paragraph("Moy, J. (1998). <i>OSPF Version 2</i> (RFC 2328). Internet Engineering "
                  "Task Force. https://www.rfc-editor.org/rfc/rfc2328", ST["ref"]),
        Paragraph("Saint-Andre, P. (2011). <i>Extensible Messaging and Presence Protocol "
                  "(XMPP): Core</i> (RFC 6120). Internet Engineering Task Force. "
                  "https://www.rfc-editor.org/rfc/rfc6120", ST["ref"]),
        Paragraph("Python Software Foundation. (2026). <i>asyncio &mdash; Asynchronous I/O</i>. "
                  "https://docs.python.org/3/library/asyncio.html", ST["ref"]),
    ]


# ------------------------------------------------------------------ documento

def numero_de_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    canvas.drawRightString(letter[0] - 2.5 * cm, 1.5 * cm, str(doc.page))
    canvas.restoreState()


def construir():
    doc = BaseDocTemplate(
        SALIDA, pagesize=letter,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        topMargin=2.4 * cm, bottomMargin=2.4 * cm,
        title="Laboratorio 3 - Algoritmos de Enrutamiento",
        author="Estrada, Mendizabal, Rojas, Pivaral",
        subject="CC3067 Redes - Universidad del Valle de Guatemala",
    )
    marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="cuerpo")
    doc.addPageTemplates([PageTemplate(id="normal", frames=[marco],
                                       onPage=numero_de_pagina)])

    elementos = []
    elementos += portada()
    elementos += seccion_practica()
    elementos += seccion_diseno()
    elementos += seccion_algoritmos()
    elementos += seccion_resultados()
    elementos += seccion_discusion()
    elementos += seccion_conclusiones()
    elementos += seccion_referencias()

    doc.build(elementos)
    return SALIDA


if __name__ == "__main__":
    ruta = construir()
    print("Reporte generado: {}".format(ruta))
    sys.exit(0)
