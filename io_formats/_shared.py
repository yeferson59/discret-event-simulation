"""Piezas compartidas entre los parsers/writers de `.DEF` y XML: el mismo
mapeo de parámetros por tipo de distribución y el mismo contrato de salida,
para que todos los formatos produzcan/lean redes idénticas y no se
desincronicen entre sí.
"""

from dataclasses import dataclass

from core.distributions import (
    Beta,
    Distribution,
    Empirical,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    Pareto,
    Triangular,
    TriangularInverse,
    Uniform,
    Weibull,
)
from core.models import NodeConfig

POSITIONAL_FIELDS: dict[str, list[str]] = {
    "exp": ["mean"],
    "exponential": ["mean"],
    "uniforme": ["a", "b"],
    "uniform": ["a", "b"],
    "triangular": ["low", "mode", "high"],
    "triangularinverse": ["low", "mode", "high"],
    "normal": ["mu", "sigma"],
    "lognormal": ["mean", "sigma"],
    "beta": ["a", "b"],
    "gamma": ["alpha", "beta"],
    "weibull": ["a"],
    "pareto": ["a"],
    "parento": ["a"],  # alias por typo histórico, para archivos viejos
}

TABLE_KINDS = {"tabla", "table"}

# Clave canónica de salida por clase de distribución, usada por los writers
# (`def_writer.py`) para ir de una instancia ya construida de vuelta al texto
# de entrada. Es la inversa del `registry` de `Distribution.from_spec`,
# tomando una única clave por clase aunque `from_spec` acepte sinónimos.
CANONICAL_KIND: dict[type[Distribution], str] = {
    Exponential: "exp",
    Uniform: "uniform",
    Triangular: "triangular",
    TriangularInverse: "triangularinverse",
    Normal: "normal",
    LogNormal: "lognormal",
    Beta: "beta",
    Gamma: "gamma",
    Weibull: "weibull",
    Pareto: "pareto",
    Empirical: "tabla",
}


@dataclass
class ParsedNetwork:
    """Resultado de parsear un `.DEF` o un XML: la red lista para
    `core.engine.Engine`."""

    nodes: list[NodeConfig]
    sim_time: float
    initial_clients: int


def dump_distribution(dist: Distribution) -> tuple[str, dict[str, object]]:
    """Devuelve `(kind, params)` de una distribución ya construida: el
    inverso de `Distribution.from_spec`. Único lugar que sabe traducir una
    instancia de vuelta a su representación kind+params, para que
    `def_writer.py` (texto `.DEF`) y `ui/editor_bridge.py` (JSON del editor
    visual) no dupliquen esa lógica cada uno a su manera."""
    kind = CANONICAL_KIND.get(type(dist))
    if kind is None:
        raise ValueError(f"No hay clave de salida registrada para {type(dist).__name__}")

    if kind == "tabla":
        return kind, {"values": list(dist.values), "cum_probs": list(dist.cum_probs)}  # type: ignore[attr-defined]

    field_names = POSITIONAL_FIELDS[kind]
    return kind, {name: getattr(dist, name) for name in field_names}
