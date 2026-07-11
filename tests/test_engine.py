import pytest

from core.distributions import Exponential, Uniform
from core.engine import Engine
from core.models import NodeConfig
from core.stats import TraceEventType


def const(value: float) -> Uniform:
    """Distribución determinística: Uniform(a, a) siempre devuelve `a`."""
    return Uniform(a=value, b=value)


def test_rejects_non_positive_sim_time():
    node = NodeConfig(id=1, service=const(1.0), arrival=const(1.0))
    with pytest.raises(ValueError):
        Engine([node], sim_time=0)


def test_rejects_successor_referencing_unknown_node():
    node = NodeConfig(
        id=1, service=const(1.0), arrival=const(1.0), succ=[99], prob=[1.0]
    )
    with pytest.raises(ValueError):
        Engine([node], sim_time=10)


def test_single_server_no_queue_when_service_faster_than_arrivals():
    # Llegadas cada 5, servicio de 2: nunca hay cola.
    node = NodeConfig(id=1, service=const(2.0), arrival=const(5.0), cap=1)
    stats = Engine([node], sim_time=20).run()

    summary = stats.summary(sim_time=20)
    assert summary.entities_created == 4  # llegadas en t=5,10,15,20
    assert summary.entities_completed == 3  # la 4a no termina antes de t=20
    assert summary.avg_time_in_system == pytest.approx(2.0)
    assert summary.avg_wait_time == pytest.approx(0.0)

    node_stats = stats.node(1)
    assert node_stats.arrivals == 4
    assert node_stats.completions == 3
    assert node_stats.avg_queue_length == pytest.approx(0.0)
    assert node_stats.utilization == pytest.approx(6.0 / 20.0)


def test_queue_builds_when_service_slower_than_arrivals():
    # Llegadas cada 1, servicio de 3, un solo servidor: debe formarse cola.
    node = NodeConfig(id=1, service=const(3.0), arrival=const(1.0), cap=1)
    stats = Engine([node], sim_time=30).run()

    node_stats = stats.node(1)
    assert node_stats.arrivals > node_stats.completions
    assert node_stats.avg_queue_length > 0
    assert node_stats.utilization == pytest.approx(1.0, abs=0.05)


def test_more_servers_reduce_queueing():
    def build_stats(cap: int):
        node = NodeConfig(id=1, service=const(3.0), arrival=const(1.0), cap=cap)
        return Engine([node], sim_time=30).run().node(1)

    single_server = build_stats(cap=1)
    multi_server = build_stats(cap=3)

    assert multi_server.avg_queue_length < single_server.avg_queue_length


def test_two_node_chain_accumulates_service_and_wait_times():
    node1 = NodeConfig(
        id=1, service=const(1.0), arrival=const(4.0), succ=[2], prob=[1.0]
    )
    node2 = NodeConfig(id=2, service=const(2.0))
    stats = Engine([node1, node2], sim_time=10).run()

    summary = stats.summary(sim_time=10)
    assert summary.entities_created == 2
    assert summary.entities_completed == 1
    assert summary.avg_time_in_system == pytest.approx(3.0)
    assert summary.avg_wait_time == pytest.approx(0.0)
    assert summary.avg_service_time == pytest.approx(3.0)

    assert stats.node(1).arrivals == 2
    assert stats.node(1).completions == 2
    assert stats.node(2).arrivals == 2
    assert stats.node(2).completions == 1


def test_routing_splits_between_successors_by_probability():
    source = NodeConfig(
        id=1, service=const(0.1), arrival=const(1.0), succ=[2, 3], prob=[0.5, 1.0]
    )
    branch_a = NodeConfig(id=2, service=const(0.1), cap=1000)
    branch_b = NodeConfig(id=3, service=const(0.1), cap=1000)

    stats = Engine([source, branch_a, branch_b], sim_time=50, seed=42).run()

    departures_from_source = stats.node(1).completions
    arrivals_a = stats.node(2).arrivals
    arrivals_b = stats.node(3).arrivals

    assert arrivals_a + arrivals_b == departures_from_source
    assert arrivals_a > 0
    assert arrivals_b > 0


def test_trace_records_full_lifecycle_when_no_queueing():
    # Llegadas cada 5, servicio de 2, cap=1: nunca hay cola, así que cada
    # entidad debe dejar ARRIVAL + SERVICE_START en el mismo instante y
    # DEPARTURE + EXIT dos unidades después (nodo único = sink).
    node = NodeConfig(id=1, service=const(2.0), arrival=const(5.0), cap=1)
    stats = Engine([node], sim_time=20).run()

    # La 4a entidad (llega en t=20) alcanza a entrar a servicio pero su
    # salida en t=22 cae fuera de sim_time, así que no deja DEPARTURE/EXIT.
    assert len(stats.trace) == 4 * 2 + 3 * 2

    entity_1_events = [e for e in stats.trace if e.entity_id == 1]
    assert [e.event_type for e in entity_1_events] == [
        TraceEventType.ARRIVAL,
        TraceEventType.SERVICE_START,
        TraceEventType.DEPARTURE,
        TraceEventType.EXIT,
    ]
    assert [e.time for e in entity_1_events] == [5.0, 5.0, 7.0, 7.0]
    assert all(e.node_id == 1 for e in entity_1_events)

    assert not any(e.event_type is TraceEventType.QUEUED for e in stats.trace)


def test_trace_records_queued_event_when_server_is_busy():
    # Llegadas cada 1, servicio de 3, un solo servidor: la 2a entidad debe
    # esperar, así que debe dejar un evento QUEUED antes de SERVICE_START.
    node = NodeConfig(id=1, service=const(3.0), arrival=const(1.0), cap=1)
    stats = Engine([node], sim_time=10).run()

    queued_events = [e for e in stats.trace if e.event_type is TraceEventType.QUEUED]
    assert len(queued_events) > 0

    entity_2_events = [e for e in stats.trace if e.entity_id == 2]
    assert TraceEventType.QUEUED in [e.event_type for e in entity_2_events]
    assert entity_2_events[0].event_type is TraceEventType.ARRIVAL
    assert entity_2_events[1].event_type is TraceEventType.QUEUED


def test_trace_exit_only_recorded_at_sink_node():
    node1 = NodeConfig(
        id=1, service=const(1.0), arrival=const(4.0), succ=[2], prob=[1.0]
    )
    node2 = NodeConfig(id=2, service=const(2.0))
    stats = Engine([node1, node2], sim_time=10).run()

    exit_events = [e for e in stats.trace if e.event_type is TraceEventType.EXIT]
    assert len(exit_events) == 1
    assert exit_events[0].node_id == 2  # solo el sink genera EXIT, no node1

    departures_node1 = [
        e
        for e in stats.trace
        if e.node_id == 1 and e.event_type is TraceEventType.DEPARTURE
    ]
    assert len(departures_node1) == 2  # ambas entidades salen de node1...
    assert not any(
        e.node_id == 1 and e.event_type is TraceEventType.EXIT for e in stats.trace
    )  # ...pero ninguna sale del sistema ahí, porque node1 no es sink


def test_trace_events_are_chronologically_ordered():
    node = NodeConfig(id=1, service=const(3.0), arrival=const(1.0), cap=1)
    stats = Engine([node], sim_time=10).run()

    times = [e.time for e in stats.trace]
    assert times == sorted(times)


def test_system_arrival_and_completion_series_are_cumulative():
    node = NodeConfig(id=1, service=const(2.0), arrival=const(5.0), cap=1)
    stats = Engine([node], sim_time=20).run()

    assert stats.system_arrivals == [(5.0, 1), (10.0, 2), (15.0, 3), (20.0, 4)]
    assert stats.system_completions == [(7.0, 1), (12.0, 2), (17.0, 3)]


def test_same_seed_reproduces_identical_run_including_sampled_times():
    # La semilla debe fijar la corrida completa: tanto el enrutamiento como
    # los tiempos muestreados por las distribuciones (llegadas y servicio).
    def build_network() -> list[NodeConfig]:
        source = NodeConfig(
            id=1,
            service=Exponential(mean=1.0),
            arrival=Exponential(mean=2.0),
            succ=[2, 3],
            prob=[0.5, 1.0],
        )
        return [
            source,
            NodeConfig(id=2, service=Exponential(mean=1.5)),
            NodeConfig(id=3, service=Exponential(mean=0.5)),
        ]

    stats_a = Engine(build_network(), sim_time=100, seed=7).run()
    stats_b = Engine(build_network(), sim_time=100, seed=7).run()

    assert stats_a.trace == stats_b.trace
    assert stats_a.system_arrivals == stats_b.system_arrivals
    assert stats_a.system_completions == stats_b.system_completions
    for node_id in (1, 2, 3):
        assert stats_a.node(node_id).utilization == stats_b.node(node_id).utilization


def test_system_completions_only_counted_once_per_entity_in_multi_node_chain():
    node1 = NodeConfig(
        id=1, service=const(1.0), arrival=const(4.0), succ=[2], prob=[1.0]
    )
    node2 = NodeConfig(id=2, service=const(2.0))
    stats = Engine([node1, node2], sim_time=10).run()

    assert stats.system_arrivals == [(4.0, 1), (8.0, 2)]
    assert stats.system_completions == [(7.0, 1)]
