import pytest

from core.distributions import Uniform
from core.models import Entity, NodeConfig
from core.stats import NodeStats, StatsCollector, TraceEventType, avg


def const(value: float) -> Uniform:
    """Distribución determinística: Uniform(a, a) siempre devuelve `a`."""
    return Uniform(a=value, b=value)


def test_avg_returns_none_for_empty_list():
    assert avg([]) is None


def test_avg_computes_mean():
    assert avg([1.0, 2.0, 3.0]) == pytest.approx(2.0)


def test_node_stats_defaults_to_zero_before_any_record():
    ns = NodeStats(node_id=1, cap=2)
    assert ns.avg_queue_length == 0.0
    assert ns.utilization == 0.0


def test_node_stats_avg_queue_length_and_utilization_are_time_weighted():
    ns = NodeStats(node_id=1, cap=1)
    ns.record(time=0.0, queue_length=0, busy_servers=0)
    ns.record(time=2.0, queue_length=2, busy_servers=1)
    ns.finalize(end_time=10.0)

    # Cola=2 durante [2,10) de un total de 10: area=16, promedio=1.6
    assert ns.avg_queue_length == pytest.approx(1.6)
    # Ocupado durante [2,10) de un total de 10 con cap=1: 0.8
    assert ns.utilization == pytest.approx(0.8)


def test_record_event_appends_to_trace():
    node = NodeConfig(id=1, service=const(1.0))
    collector = StatsCollector([node])

    collector.record_event(1.5, node_id=1, event_type=TraceEventType.ARRIVAL, entity_id=7)

    assert len(collector.trace) == 1
    record = collector.trace[0]
    assert record.time == 1.5
    assert record.node_id == 1
    assert record.event_type is TraceEventType.ARRIVAL
    assert record.entity_id == 7


def test_record_system_arrival_and_completion_are_cumulative():
    node = NodeConfig(id=1, service=const(1.0))
    collector = StatsCollector([node])

    collector.record_system_arrival(1.0)
    collector.record_system_arrival(3.0)
    collector.record_system_completion(5.0)

    assert collector.system_arrivals == [(1.0, 1), (3.0, 2)]
    assert collector.system_completions == [(5.0, 1)]


def test_summary_includes_zero_time_in_system_entities():
    # Regresión: antes se usaba `if e.time_in_system` para filtrar, y como
    # 0.0 es falsy en Python, las entidades con tiempo en sistema exactamente
    # 0 se excluían silenciosamente del promedio.
    node = NodeConfig(id=1, service=const(1.0))
    collector = StatsCollector([node])

    e1 = Entity(id=1, entry_time=0.0, current_node=1)
    e1.finalize(exit_time=0.0)
    e2 = Entity(id=2, entry_time=0.0, current_node=1)
    e2.finalize(exit_time=4.0)
    collector.register_entity(e1)
    collector.register_entity(e2)
    collector.finalize(end_time=10.0)

    summary = collector.summary(sim_time=10.0)
    assert summary.entities_completed == 2
    assert summary.avg_time_in_system == pytest.approx(2.0)  # (0.0 + 4.0) / 2


def test_summary_excludes_entities_still_in_progress():
    node = NodeConfig(id=1, service=const(1.0))
    collector = StatsCollector([node])

    e1 = Entity(id=1, entry_time=0.0, current_node=1)
    e1.finalize(exit_time=5.0)
    e2 = Entity(id=2, entry_time=3.0, current_node=1)  # nunca sale del sistema
    collector.register_entity(e1)
    collector.register_entity(e2)
    collector.finalize(end_time=10.0)

    summary = collector.summary(sim_time=10.0)
    assert summary.entities_created == 2
    assert summary.entities_completed == 1
    assert summary.avg_time_in_system == pytest.approx(5.0)
