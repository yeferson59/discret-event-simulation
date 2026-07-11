"""Parser del formato de entrada XML (equivalente en información al `.DEF`
extendido — mismo contrato de salida: `ParsedNetwork` con `list[NodeConfig]`).

Esquema:

    <simulation sim_time="20" initial_clients="0">
      <node id="1" cap="1">
        <arrival kind="exp" mean="5.0"/>
        <service kind="uniform" a="1.0" b="10.0"/>
        <successors>
          <successor id="2" prob="0.6"/>
          <successor id="3" prob="1.0"/>
        </successors>
      </node>
      <node id="2" cap="1">
        <service kind="tabla">
          <value v="1.0" prob="0.3"/>
          <value v="2.0" prob="0.7"/>
          <value v="3.0" prob="1.0"/>
        </service>
      </node>
    </simulation>

- `<arrival>` es opcional: su ausencia equivale al nodo sin llegadas externas
  del `.DEF` (línea de 2 campos en vez de 3).
- `<successors>` es opcional o puede quedar vacío: ambos casos son un nodo
  sink, igual que `cantidad_sucesores=0` en el `.DEF`.
- El atributo `kind` de `<arrival>`/`<service>` acepta las mismas claves que
  `Distribution.from_spec`. Los parámetros van como atributos del propio
  elemento (mismos nombres que los campos de `core.distributions`, ver
  `io_formats._shared.POSITIONAL_FIELDS`), excepto la distribución tipo
  tabla, cuyos pares valor/probabilidad van como elementos hijos `<value>`.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

from core.distributions import Distribution
from core.models import NodeConfig
from io_formats._shared import POSITIONAL_FIELDS, TABLE_KINDS, ParsedNetwork


def parse_xml_file(path: str | Path) -> ParsedNetwork:
    """Lee y parsea un archivo XML desde disco."""
    return parse_xml_text(Path(path).read_text(encoding="utf-8"))


def parse_xml_text(text: str) -> ParsedNetwork:
    """Parsea el contenido de un XML ya leído como string."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"XML inválido: {exc}") from exc

    if root.tag != "simulation":
        raise ValueError(
            f"Se esperaba <simulation> como raíz, se encontró <{root.tag}>"
        )

    sim_time = float(_require_attr(root, "sim_time", context="<simulation>"))
    initial_clients = int(_require_attr(root, "initial_clients", context="<simulation>"))
    if initial_clients != 0:
        raise ValueError(
            f"initial_clients={initial_clients} no soportado: el motor aún no "
            "admite entidades precargadas en t=0"
        )

    nodes = [_parse_node_element(node_elem) for node_elem in root.findall("node")]

    return ParsedNetwork(nodes=nodes, sim_time=sim_time, initial_clients=initial_clients)


def _parse_node_element(elem: ET.Element) -> NodeConfig:
    node_id = int(_require_attr(elem, "id", context="<node>"))
    cap = int(elem.get("cap", "1"))

    service_elem = elem.find("service")
    if service_elem is None:
        raise ValueError(f"Nodo {node_id}: falta <service>")
    service = _parse_distribution_element(service_elem)

    arrival_elem = elem.find("arrival")
    arrival = (
        _parse_distribution_element(arrival_elem) if arrival_elem is not None else None
    )

    succ: list[int] = []
    prob: list[float] = []
    successors_elem = elem.find("successors")
    if successors_elem is not None:
        for succ_elem in successors_elem.findall("successor"):
            context = f"nodo {node_id} <successor>"
            succ.append(int(_require_attr(succ_elem, "id", context=context)))
            prob.append(float(_require_attr(succ_elem, "prob", context=context)))

    return NodeConfig(
        id=node_id, service=service, cap=cap, arrival=arrival, succ=succ, prob=prob
    )


def _parse_distribution_element(elem: ET.Element) -> Distribution:
    kind = _require_attr(elem, "kind", context=f"<{elem.tag}>")
    kind_key = kind.strip().lower()

    if kind_key in TABLE_KINDS:
        values: list[float] = []
        cum_probs: list[float] = []
        for value_elem in elem.findall("value"):
            values.append(float(_require_attr(value_elem, "v", context="<value>")))
            cum_probs.append(
                float(_require_attr(value_elem, "prob", context="<value>"))
            )
        return Distribution.from_spec(
            kind_key, {"values": values, "cum_probs": cum_probs}
        )

    if kind_key not in POSITIONAL_FIELDS:
        raise ValueError(f"Distribución desconocida en XML: '{kind}'")

    field_names = POSITIONAL_FIELDS[kind_key]
    params = {
        name: float(_require_attr(elem, name, context=f"<{elem.tag} kind='{kind}'>"))
        for name in field_names
    }
    return Distribution.from_spec(kind_key, params)


def _require_attr(elem: ET.Element, name: str, context: str) -> str:
    value = elem.get(name)
    if value is None:
        raise ValueError(f"{context}: falta el atributo '{name}'")
    return value
