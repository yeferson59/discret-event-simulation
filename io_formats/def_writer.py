"""Serializa `list[NodeConfig]` de vuelta al formato de texto `.DEF`
extendido que lee `io_formats.def_parser`.

Cierra la funcionalidad #1 (formulario que genera un `.def`): el editor
visual (`ui/`) arma la red en memoria y usa este módulo para escribirla a
disco. Sigue el mismo patrón `format_*`/`write_*_file` que ya usan
`report_writer.py` y `def_parser.py`.
"""

from pathlib import Path

from core.distributions import Distribution
from core.models import NodeConfig
from io_formats._shared import dump_distribution


def format_def_text(
    nodes: list[NodeConfig], sim_time: float, initial_clients: int = 0
) -> str:
    """Genera el texto `.DEF` equivalente a `nodes` (inverso de
    `def_parser.parse_def_text`)."""
    lines = [f"{sim_time} {initial_clients}"]

    for node in nodes:
        lines.append(str(node.id))

        service_tok = _format_distribution(node.service)
        if node.arrival is not None:
            arrival_tok = _format_distribution(node.arrival)
            lines.append(f"{arrival_tok} {service_tok} {node.cap}")
        else:
            lines.append(f"{service_tok} {node.cap}")

        lines.append(str(len(node.succ)))
        lines.append(" ".join(str(s) for s in node.succ))
        lines.append(" ".join(str(p) for p in node.prob))

    return "\n".join(lines) + "\n"


def write_def_file(
    nodes: list[NodeConfig],
    sim_time: float,
    path: str | Path,
    initial_clients: int = 0,
) -> None:
    """Escribe a disco el `.DEF` generado por `format_def_text`."""
    Path(path).write_text(
        format_def_text(nodes, sim_time, initial_clients), encoding="utf-8"
    )


def _format_distribution(dist: Distribution) -> str:
    kind, params = dump_distribution(dist)

    if kind == "tabla":
        pairs = ";".join(f"{v}:{p}" for v, p in zip(params["values"], params["cum_probs"]))
        return f"tabla:{pairs}"

    if kind == "exp":
        return str(params["mean"])

    return f"{kind}:{','.join(str(v) for v in params.values())}"
