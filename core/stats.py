"""Recolector de estadísticas y series de tiempo del motor DES.

El motor (`core/engine.py`) es la única capa que escribe aquí; todo lo demás
(reportes, gráficas) solo lee un `StatsCollector` ya finalizado. Las métricas
por nodo se acumulan como integrales en el tiempo (área bajo la curva) para
poder calcular promedios ponderados por tiempo sin guardar cada evento.
"""

from dataclasses import dataclass, field
from enum import Enum

from core.models import Entity, NodeConfig


class TraceEventType(Enum):
    """Tipo semántico de un evento en la traza (funcionalidad #5), distinto
    de `EventType` en el motor (que solo distingue eventos de la cola de
    simulación, no lo que representan para un reporte)."""

    ARRIVAL = "llegada"
    QUEUED = "cola"
    SERVICE_START = "inicio_servicio"
    DEPARTURE = "fin_servicio"
    EXIT = "salida_sistema"


@dataclass
class EventRecord:
    """Una línea de la traza cruda de eventos: (tiempo, nodo, tipo, entidad)."""

    time: float
    node_id: int
    event_type: TraceEventType
    entity_id: int


@dataclass
class NodeSnapshot:
    """Estado de un nodo inmediatamente después de un evento, para graficar."""

    time: float
    queue_length: int
    busy_servers: int


@dataclass
class NodeStats:
    """Estadísticas acumuladas de un nodo a lo largo de la simulación."""

    node_id: int
    cap: int

    arrivals: int = 0
    completions: int = 0

    history: list[NodeSnapshot] = field(default_factory=list)

    _queue_area: float = 0.0
    _busy_area: float = 0.0
    _last_time: float = 0.0
    _queue_length: int = 0
    _busy_servers: int = 0

    def _advance(self, time: float) -> None:
        dt = time - self._last_time

        if dt > 0:
            self._queue_area += self._queue_length * dt
            self._busy_area += self._busy_servers * dt

        self._last_time = time

    def record(self, time: float, queue_length: int, busy_servers: int) -> None:
        """Registra un cambio de estado del nodo (llamado por el motor)."""
        self._advance(time)
        self._queue_length = queue_length
        self._busy_servers = busy_servers
        self.history.append(NodeSnapshot(time, queue_length, busy_servers))

    def finalize(self, end_time: float) -> None:
        """Cierra las integrales de tiempo hasta el fin de la simulación."""
        self._advance(end_time)

    @property
    def avg_queue_length(self) -> float:
        return (self._queue_area / self._last_time) if self._last_time > 0 else 0.0

    @property
    def utilization(self) -> float:
        if self._last_time <= 0 or self.cap <= 0:
            return 0.0

        return self._busy_area / (self._last_time * self.cap)


@dataclass
class SimulationSummary:
    """Resumen agregado de una corrida, listo para reporte o UI."""

    sim_time: float
    entities_created: int
    entities_completed: int
    avg_time_in_system: float | None
    avg_wait_time: float | None
    avg_service_time: float | None
    per_node: dict[int, NodeStats]


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


class StatsCollector:
    """Acumula estadísticas por nodo y por entidad durante una corrida."""

    def __init__(self, nodes: list[NodeConfig]):
        self.node_stats: dict[int, NodeStats] = {
            n.id: NodeStats(node_id=n.id, cap=n.cap) for n in nodes
        }

        self.entities: dict[int, Entity] = {}

        self.trace: list[EventRecord] = []
        # Serie temporal acumulada: cada tupla es (tiempo, conteo_acumulado).
        self.system_arrivals: list[tuple[float, int]] = []
        self.system_completions: list[tuple[float, int]] = []

    def node(self, node_id: int) -> NodeStats:
        return self.node_stats[node_id]

    def register_entity(self, entity: Entity) -> None:
        self.entities[entity.id] = entity

    def record_event(
        self, time: float, node_id: int, event_type: TraceEventType, entity_id: int
    ) -> None:
        """Agrega una línea a la traza cruda de eventos (funcionalidad #5)."""
        self.trace.append(EventRecord(time, node_id, event_type, entity_id))

    def record_system_arrival(self, time: float) -> None:
        """Registra la llegada de una entidad nueva al sistema (funcionalidad #7)."""
        self.system_arrivals.append((time, len(self.system_arrivals) + 1))

    def record_system_completion(self, time: float) -> None:
        """Registra la salida de una entidad del sistema (funcionalidad #7)."""
        self.system_completions.append((time, len(self.system_completions) + 1))

    def finalize(self, end_time: float) -> None:
        for node_stats in self.node_stats.values():
            node_stats.finalize(end_time)

    def summary(self, sim_time: float) -> SimulationSummary:
        completed = [e for e in self.entities.values() if e.exit_time is not None]

        return SimulationSummary(
            sim_time=sim_time,
            entities_created=len(self.entities),
            entities_completed=len(completed),
            avg_time_in_system=avg([e.time_in_system for e in completed]),
            avg_wait_time=avg([e.total_wait_time for e in completed]),
            avg_service_time=avg([e.total_service_time for e in completed]),
            per_node=self.node_stats,
        )
