"""Motor de simulación de eventos discretos (DES).

Usa `heapq` como cola de eventos ordenada por tiempo. Cada nodo con
`cap > 1` se modela como `cap` servidores idénticos en paralelo compartiendo
una única cola FIFO (disciplina tipo M/M/c): si hay un servidor libre la
entidad entra a servicio de inmediato; si no, espera en la cola del nodo.

La simulación corre hasta `sim_time` (parada por tiempo fijo). Los eventos
programados más allá de `sim_time` se descartan al programarlos, así que el
heap siempre converge sin necesidad de un chequeo aparte en el loop.
"""

import heapq
import itertools
import random
from dataclasses import dataclass, field
from enum import Enum, auto

from core.models import Entity, NodeConfig
from core.stats import StatsCollector, TraceEventType


class EventType(Enum):
    ARRIVAL = auto()
    DEPARTURE = auto()


@dataclass(order=True)
class Event:
    time: float
    seq: int
    type: EventType = field(compare=False)
    node_id: int = field(compare=False)
    # None => crear una entidad nueva (llegada externa a un nodo fuente).
    entity_id: int | None = field(compare=False)


@dataclass
class _NodeRuntime:
    """Estado mutable de un nodo durante la corrida (no es una estadística)."""

    queue: list[int] = field(default_factory=list)
    busy: int = 0
    enqueue_time: dict[int, float] = field(default_factory=dict)


class Engine:
    """Motor DES genérico sobre una red de `NodeConfig`."""

    def __init__(
        self, nodes: list[NodeConfig], sim_time: float, seed: int | None = None
    ):
        if sim_time <= 0:
            raise ValueError("sim_time debe ser > 0")

        self.nodes: dict[int, NodeConfig] = {n.id: n for n in nodes}
        self.sim_time = sim_time

        for node in nodes:
            for succ_id in node.succ:
                if succ_id not in self.nodes:
                    raise ValueError(
                        f"Nodo {node.id}: sucesor {succ_id} no existe en la red"
                    )

        if seed is not None:
            random.seed(seed)

        self._runtime: dict[int, _NodeRuntime] = {n.id: _NodeRuntime() for n in nodes}
        self._heap: list[Event] = []
        self._seq = itertools.count()
        self._next_entity_id = itertools.count(1)
        self.now = 0.0
        self.stats = StatsCollector(nodes)

    def run(self) -> StatsCollector:
        for node in self.nodes.values():
            if node.is_source():
                if node.arrival:
                    self._schedule(
                        node.arrival.sample(), EventType.ARRIVAL, node.id, None
                    )

        while self._heap:
            event = heapq.heappop(self._heap)
            self.now = event.time
            if event.type is EventType.ARRIVAL:
                self._handle_arrival(event)
            else:
                self._handle_departure(event)

        self.stats.finalize(self.sim_time)
        return self.stats

    def _schedule(
        self, time: float, type_: EventType, node_id: int, entity_id: int | None
    ) -> None:
        if time > self.sim_time:
            return
        heapq.heappush(
            self._heap, Event(time, next(self._seq), type_, node_id, entity_id)
        )

    def _handle_arrival(self, event: Event) -> None:
        node = self.nodes[event.node_id]
        runtime = self._runtime[event.node_id]

        if event.entity_id is None:
            entity_id = next(self._next_entity_id)
            entity = Entity(id=entity_id, entry_time=self.now, current_node=node.id)
            self.stats.register_entity(entity)
            self.stats.record_system_arrival(self.now)
            next_time = self.now
            if node.arrival:
                next_time += node.arrival.sample()
            self._schedule(next_time, EventType.ARRIVAL, node.id, None)
        else:
            entity_id = event.entity_id
            self.stats.entities[entity_id].current_node = node.id

        self.stats.node(node.id).arrivals += 1
        self.stats.record_event(self.now, node.id, TraceEventType.ARRIVAL, entity_id)
        self._enqueue_or_start(node, runtime, entity_id)

    def _handle_departure(self, event: Event) -> None:
        assert event.entity_id is not None
        node = self.nodes[event.node_id]
        runtime = self._runtime[event.node_id]
        entity = self.stats.entities[event.entity_id]

        runtime.busy -= 1
        self.stats.node(node.id).completions += 1
        self._record_node_state(node.id, runtime)
        self.stats.record_event(self.now, node.id, TraceEventType.DEPARTURE, entity.id)

        next_node_id = self._route(node)
        if next_node_id is None:
            entity.finalize(exit_time=self.now)
            self.stats.record_event(self.now, node.id, TraceEventType.EXIT, entity.id)
            self.stats.record_system_completion(self.now)
        else:
            self._schedule(self.now, EventType.ARRIVAL, next_node_id, entity.id)

        if runtime.queue:
            waiting_id = runtime.queue.pop(0)
            wait = self.now - runtime.enqueue_time.pop(waiting_id)
            self.stats.entities[waiting_id].register_wait(wait)
            self._start_service(node, runtime, waiting_id)

    def _enqueue_or_start(
        self, node: NodeConfig, runtime: _NodeRuntime, entity_id: int
    ) -> None:
        if runtime.busy < node.cap:
            self._start_service(node, runtime, entity_id)
        else:
            runtime.queue.append(entity_id)
            runtime.enqueue_time[entity_id] = self.now
            self._record_node_state(node.id, runtime)
            self.stats.record_event(self.now, node.id, TraceEventType.QUEUED, entity_id)

    def _start_service(
        self, node: NodeConfig, runtime: _NodeRuntime, entity_id: int
    ) -> None:
        runtime.busy += 1
        self._record_node_state(node.id, runtime)
        self.stats.record_event(
            self.now, node.id, TraceEventType.SERVICE_START, entity_id
        )
        duration = node.service.sample()
        self.stats.entities[entity_id].register_service(duration)
        self._schedule(self.now + duration, EventType.DEPARTURE, node.id, entity_id)

    def _route(self, node: NodeConfig) -> int | None:
        if node.is_sink():
            return None
        r = random.random()
        for succ_id, cum_p in zip(node.succ, node.prob):
            if r <= cum_p:
                return succ_id
        return node.succ[-1]

    def _record_node_state(self, node_id: int, runtime: _NodeRuntime) -> None:
        self.stats.node(node_id).record(
            self.now, queue_length=len(runtime.queue), busy_servers=runtime.busy
        )
