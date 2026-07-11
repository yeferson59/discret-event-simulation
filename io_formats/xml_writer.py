"""Serializa `list[NodeConfig]` al formato de entrada XML que lee
`io_formats.xml_parser` (mismo esquema documentado en su docstring).

Es el inverso de `xml_parser.parse_xml_text`, siguiendo el mismo patrón
`format_*`/`write_*_file` que ya usan `def_writer.py` y `report_writer.py`,
para que ambos formatos de entrada (funcionalidades #1 y #2) tengan ida y
vuelta simétrica.
"""

from pathlib import Path
from xml.etree import ElementTree as ET
from xml.dom import minidom

from core.distributions import Distribution
from core.models import NodeConfig
from io_formats._shared import dump_distribution


def format_xml_text(
    nodes: list[NodeConfig], sim_time: float, initial_clients: int = 0
) -> str:
    """Genera el texto XML equivalente a `nodes` (inverso de
    `xml_parser.parse_xml_text`)."""
    root = ET.Element(
        "simulation",
        {"sim_time": _fmt_number(sim_time), "initial_clients": str(initial_clients)},
    )

    for node in nodes:
        node_elem = ET.SubElement(
            root, "node", {"id": str(node.id), "cap": str(node.cap)}
        )
        if node.arrival is not None:
            _append_distribution(node_elem, "arrival", node.arrival)
        _append_distribution(node_elem, "service", node.service)

        if node.succ:
            successors_elem = ET.SubElement(node_elem, "successors")
            for succ_id, prob in zip(node.succ, node.prob):
                ET.SubElement(
                    successors_elem,
                    "successor",
                    {"id": str(succ_id), "prob": _fmt_number(prob)},
                )

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def write_xml_file(
    nodes: list[NodeConfig],
    sim_time: float,
    path: str | Path,
    initial_clients: int = 0,
) -> None:
    """Escribe a disco el XML generado por `format_xml_text`."""
    Path(path).write_text(
        format_xml_text(nodes, sim_time, initial_clients), encoding="utf-8"
    )


def _append_distribution(parent: ET.Element, tag: str, dist: Distribution) -> ET.Element:
    kind, params = dump_distribution(dist)

    if kind == "tabla":
        elem = ET.SubElement(parent, tag, {"kind": kind})
        for value, prob in zip(params["values"], params["cum_probs"]):
            ET.SubElement(
                elem, "value", {"v": _fmt_number(value), "prob": _fmt_number(prob)}
            )
        return elem

    attrs = {"kind": kind} | {name: _fmt_number(v) for name, v in params.items()}
    return ET.SubElement(parent, tag, attrs)


def _fmt_number(value: float) -> str:
    return str(value)
