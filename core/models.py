"""Modelos de datos centrales para el simulador de eventos discretos.

Estas estructuras son el contrato entre las capas de entrada (parsers .DEF/XML),
el motor de simulación y las capas de salida (reportes, gráficas). Ninguna otra
capa debe inventar su propia representación de un nodo o una entidad: todo
parser debe producir una lista de NodeConfig, y el motor debe producir/actualizar
objetos Entity para poder calcular estadísticas globales por entidad (#9).
"""

from dataclasses import dataclass, field

from core.distributions import Distribution


@dataclass
class NodeConfig:
    """Configuración estática de un nodo/proceso, leída de un archivo de entrada."""

    id: int
    service: Distribution
    cap: int = 1
    arrival: Distribution | None = None  # None => no hay llegadas externas a este nodo
    succ: list[int] = field(default_factory=list)
    prob: list[float] = field(default_factory=list)  # acumuladas, mismo largo que succ

    def __post_init__(self) -> None:
        if len(self.succ) != len(self.prob):
            raise ValueError(
                f"Nodo {self.id}: succ y prob deben tener el mismo tamaño "
                f"({len(self.succ)} vs {len(self.prob)})"
            )
        if self.prob and abs(self.prob[-1] - 1.0) > 1e-6:
            raise ValueError(
                f"Nodo {self.id}: la última probabilidad acumulada debe ser 1.0, "
                f"es {self.prob[-1]}"
            )
        if self.cap < 1:
            raise ValueError(f"Nodo {self.id}: la capacidad debe ser >= 1")

    def is_source(self) -> bool:
        """True si el nodo recibe llegadas externas."""
        return self.arrival is not None

    def is_sink(self) -> bool:
        """True si el nodo no enruta a ningún otro (fin de camino para una entidad)."""
        return not self.succ


@dataclass
class Entity:
    """Una entidad individual que atraviesa la red.

    Se crea en el momento de una llegada externa y se actualiza en cada nodo
    que visita. Es la pieza que el motor original no tenía: antes solo se
    llevaban contadores agregados por nodo, lo que hace imposible calcular
    tiempo en el sistema, tiempo en cola total y tiempo de servicio total de
    una entidad a través de toda la red (funcionalidad #9).
    """

    id: int
    entry_time: float
    current_node: int

    total_wait_time: float = 0.0
    total_service_time: float = 0.0
    exit_time: float | None = None

    def register_wait(self, wait: float) -> None:
        self.total_wait_time += wait

    def register_service(self, duration: float) -> None:
        self.total_service_time += duration

    def finalize(self, exit_time: float) -> None:
        self.exit_time = exit_time

    @property
    def time_in_system(self) -> float | None:
        if self.exit_time is None:
            return None
        return self.exit_time - self.entry_time
