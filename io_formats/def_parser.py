"""Parser del formato de entrada `.DEF`.

Acepta dos variantes, auto-detectadas al parsear:

**Formato extendido** (el que escribe `io_formats.def_writer`):

    <sim_time> <clientes_iniciales>
    <id_nodo>
    <tLL> <ts> <cap>          # si el nodo tiene llegadas externas (3 campos)
    <ts> <cap>                # si no las tiene (2 campos)
    <cantidad_sucesores>
    <ids_sucesores separados por espacio>
    <probabilidades_acumuladas separadas por espacio>

Este bloque de 5 líneas se repite una vez por nodo. Un nodo sin sucesores
(sink) igual deja las líneas de ids/probabilidades, vacías. Los ids de nodo
son explícitos y deben ser únicos.

**Formato legado del profesor** (los `.DEF` originales del curso):

    <sim_time> <clientes_iniciales>
    <tipo_nodo>               # 1 = con llegadas externas, 2 = sin llegadas
    <tLL> <ts> <cap>          # si tipo 1
    <ts> <cap>                # si tipo 2
    <cantidad_sucesores>
    <ids_sucesores>           # solo presentes si cantidad_sucesores > 0
    <probabilidades_acumuladas>

Aquí no hay línea de id: los nodos se numeran implícitamente 1..N en orden
de aparición, y un sink (cantidad_sucesores = 0) omite por completo las
líneas de ids/probabilidades. El tipo es redundante con la cantidad de
campos de la línea de tiempos (3 vs 2), lo que sirve de validación cruzada.

La detección intenta primero el formato extendido; si falla (por ejemplo,
ids duplicados: en un archivo legado los "ids" leídos serían los tipos 1/2
repetidos), reintenta como legado. Un archivo legado con más de dos nodos
siempre cae al formato legado por esa validación de unicidad.

En ambas variantes, cada campo `tLL`/`ts` puede ser:
  - un número suelto, ej. `5.0` -> retrocompatible, se interpreta como la
    media de una exponencial (`Distribution.from_spec("exp", {"mean": 5.0})`);
  - `<kind>:<params>` con parámetros separados por coma, en el mismo orden
    que los campos de la clase de `core.distributions`, ej.
    `uniform:1.0,10.0`, `normal:3.0,0.5`;
  - `tabla:<valor>:<prob>;<valor>:<prob>;...` para la distribución empírica.

Se usa coma/dos-puntos (no espacios) dentro del campo de distribución para
no romper la heurística original: el número de campos separados por espacio
en la línea de servicio (2 o 3) es lo único que distingue si el nodo tiene
llegadas externas.
"""

from pathlib import Path

from core.distributions import Distribution
from core.models import NodeConfig
from io_formats._shared import POSITIONAL_FIELDS, TABLE_KINDS, ParsedNetwork


def parse_def_file(path: str | Path) -> ParsedNetwork:
    """Lee y parsea un archivo `.DEF` desde disco."""
    return parse_def_text(Path(path).read_text(encoding="utf-8"))


def parse_def_text(text: str) -> ParsedNetwork:
    """Parsea el contenido de un `.DEF` ya leído como string, auto-detectando
    entre el formato extendido y el formato legado del profesor."""
    lines = text.splitlines()

    try:
        return _parse_extended(lines)
    except ValueError as extended_error:
        try:
            return _parse_legacy(lines)
        except ValueError as legacy_error:
            raise ValueError(
                "No se pudo parsear el .DEF en ninguno de los dos formatos "
                "soportados.\n"
                f"- como formato extendido (id de nodo por bloque): {extended_error}\n"
                f"- como formato legado del profesor (tipo 1/2, ids implícitos): "
                f"{legacy_error}"
            ) from extended_error


def _parse_extended(lines: list[str]) -> ParsedNetwork:
    cursor = _LineCursor(lines)
    sim_time, initial_clients = _parse_header(cursor)

    nodes: list[NodeConfig] = []
    seen_ids: set[int] = set()
    while cursor.has_more_content():
        node = _parse_node_block(cursor)
        if node.id in seen_ids:
            raise ValueError(
                f"Id de nodo duplicado: {node.id} (¿archivo en formato legado "
                "del profesor, donde esa línea es el tipo de nodo?)"
            )
        seen_ids.add(node.id)
        nodes.append(node)

    return ParsedNetwork(nodes=nodes, sim_time=sim_time, initial_clients=initial_clients)


def _parse_legacy(lines: list[str]) -> ParsedNetwork:
    cursor = _LineCursor(lines)
    sim_time, initial_clients = _parse_header(cursor)

    nodes: list[NodeConfig] = []
    while cursor.has_more_content():
        nodes.append(_parse_legacy_node_block(cursor, node_id=len(nodes) + 1))

    return ParsedNetwork(nodes=nodes, sim_time=sim_time, initial_clients=initial_clients)


def _parse_header(cursor: "_LineCursor") -> tuple[float, int]:
    header = cursor.next_tokens()
    if len(header) != 2:
        raise ValueError(
            f"Encabezado inválido, se esperaba '<sim_time> <clientes_iniciales>': "
            f"{header}"
        )
    sim_time = float(header[0])
    initial_clients = int(header[1])
    if initial_clients != 0:
        raise ValueError(
            f"clientes_iniciales={initial_clients} no soportado: el motor aún no "
            "admite entidades precargadas en t=0"
        )
    return sim_time, initial_clients


class _LineCursor:
    """Avanza línea por línea sobre el archivo, sin descartar líneas vacías
    (una línea vacía puede ser la lista de sucesores de un nodo sink)."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._idx = 0

    def has_more_content(self) -> bool:
        return any(line.strip() for line in self._lines[self._idx :])

    def next_line(self) -> str:
        if self._idx >= len(self._lines):
            raise ValueError("Archivo .DEF incompleto: se esperaban más líneas")
        line = self._lines[self._idx]
        self._idx += 1
        return line

    def next_tokens(self) -> list[str]:
        return self.next_line().split()

    def next_tokens_or_empty(self) -> list[str]:
        """Como `next_tokens`, pero tolera EOF devolviendo `[]` en vez de
        lanzar error: un nodo sink que queda al final del archivo puede no
        tener líneas de ids/probabilidades físicamente presentes, no solo
        vacías (ej. si un editor recorta líneas en blanco finales)."""
        if self._idx >= len(self._lines):
            return []
        return self.next_line().split()


def _parse_node_block(cursor: _LineCursor) -> NodeConfig:
    id_tokens = cursor.next_tokens()
    if len(id_tokens) != 1:
        raise ValueError(f"Se esperaba un único id de nodo, se recibió: {id_tokens}")
    node_id = int(id_tokens[0])

    service_tokens = cursor.next_tokens()
    if len(service_tokens) == 3:
        arrival_tok, service_tok, cap_tok = service_tokens
        arrival = _parse_distribution(arrival_tok)
    elif len(service_tokens) == 2:
        service_tok, cap_tok = service_tokens
        arrival = None
    else:
        raise ValueError(
            f"Nodo {node_id}: se esperaban 2 o 3 campos ('ts cap' o 'tLL ts cap'), "
            f"se recibieron {len(service_tokens)}: {service_tokens}"
        )
    service = _parse_distribution(service_tok)
    cap = int(cap_tok)

    succ_count_tokens = cursor.next_tokens()
    if len(succ_count_tokens) != 1:
        raise ValueError(f"Nodo {node_id}: se esperaba un único conteo de sucesores")
    succ_count = int(succ_count_tokens[0])

    succ_tokens = cursor.next_tokens_or_empty()
    prob_tokens = cursor.next_tokens_or_empty()

    if len(succ_tokens) != succ_count or len(prob_tokens) != succ_count:
        raise ValueError(
            f"Nodo {node_id}: cantidad_sucesores={succ_count} no coincide con "
            f"{len(succ_tokens)} ids / {len(prob_tokens)} probabilidades"
        )

    succ = [int(s) for s in succ_tokens]
    prob = [float(p) for p in prob_tokens]

    return NodeConfig(
        id=node_id, service=service, cap=cap, arrival=arrival, succ=succ, prob=prob
    )


def _parse_legacy_node_block(cursor: _LineCursor, node_id: int) -> NodeConfig:
    tipo_tokens = cursor.next_tokens()
    if len(tipo_tokens) != 1 or tipo_tokens[0] not in ("1", "2"):
        raise ValueError(
            f"Nodo {node_id}: se esperaba el tipo de nodo (1=con llegadas "
            f"externas, 2=sin llegadas), se recibió: {tipo_tokens}"
        )
    tipo = int(tipo_tokens[0])

    service_tokens = cursor.next_tokens()
    if tipo == 1:
        if len(service_tokens) != 3:
            raise ValueError(
                f"Nodo {node_id}: tipo 1 requiere 'tLL ts cap' (3 campos), "
                f"se recibieron {len(service_tokens)}: {service_tokens}"
            )
        arrival_tok, service_tok, cap_tok = service_tokens
        arrival = _parse_distribution(arrival_tok)
    else:
        if len(service_tokens) != 2:
            raise ValueError(
                f"Nodo {node_id}: tipo 2 requiere 'ts cap' (2 campos), "
                f"se recibieron {len(service_tokens)}: {service_tokens}"
            )
        service_tok, cap_tok = service_tokens
        arrival = None
    service = _parse_distribution(service_tok)
    cap = int(cap_tok)

    succ_count_tokens = cursor.next_tokens()
    if len(succ_count_tokens) != 1:
        raise ValueError(f"Nodo {node_id}: se esperaba un único conteo de sucesores")
    succ_count = int(succ_count_tokens[0])

    # En el formato legado un sink (0 sucesores) no deja líneas de
    # ids/probabilidades, ni siquiera vacías: no hay que consumir nada.
    succ: list[int] = []
    prob: list[float] = []
    if succ_count > 0:
        succ_tokens = cursor.next_tokens_or_empty()
        prob_tokens = cursor.next_tokens_or_empty()
        if len(succ_tokens) != succ_count or len(prob_tokens) != succ_count:
            raise ValueError(
                f"Nodo {node_id}: cantidad_sucesores={succ_count} no coincide con "
                f"{len(succ_tokens)} ids / {len(prob_tokens)} probabilidades"
            )
        succ = [int(s) for s in succ_tokens]
        prob = [float(p) for p in prob_tokens]

    return NodeConfig(
        id=node_id, service=service, cap=cap, arrival=arrival, succ=succ, prob=prob
    )


def _parse_distribution(token: str) -> Distribution:
    token = token.strip()
    if ":" not in token:
        return Distribution.from_spec("exp", {"mean": float(token)})

    kind, params_str = token.split(":", 1)
    kind_key = kind.strip().lower()
    params_str = params_str.strip()

    if kind_key in TABLE_KINDS:
        values: list[float] = []
        cum_probs: list[float] = []
        for pair in params_str.split(";"):
            value_str, prob_str = pair.split(":")
            values.append(float(value_str.strip()))
            cum_probs.append(float(prob_str.strip()))
        return Distribution.from_spec(
            kind_key, {"values": values, "cum_probs": cum_probs}
        )

    if kind_key not in POSITIONAL_FIELDS:
        raise ValueError(f"Distribución desconocida en .DEF: '{kind}'")

    field_names = POSITIONAL_FIELDS[kind_key]
    raw_values = params_str.split(",")
    if len(raw_values) != len(field_names):
        raise ValueError(
            f"'{kind}' espera {len(field_names)} parámetros "
            f"({', '.join(field_names)}), recibió {len(raw_values)}: '{params_str}'"
        )
    params = {name: float(v) for name, v in zip(field_names, raw_values)}
    return Distribution.from_spec(kind_key, params)
