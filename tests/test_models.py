import pytest

from core.distributions import Exponential
from core.models import Entity, NodeConfig


def test_node_config_valid_routing():
    n = NodeConfig(id=1, service=Exponential(mean=2.0), succ=[2, 3], prob=[0.6, 1.0])
    assert not n.is_sink()
    assert not n.is_source()


def test_node_config_rejects_mismatched_succ_prob():
    with pytest.raises(ValueError):
        NodeConfig(id=1, service=Exponential(mean=2.0), succ=[2, 3], prob=[1.0])


def test_node_config_rejects_bad_final_prob():
    with pytest.raises(ValueError):
        NodeConfig(id=1, service=Exponential(mean=2.0), succ=[2], prob=[0.5])


def test_node_config_rejects_zero_capacity():
    with pytest.raises(ValueError):
        NodeConfig(id=1, service=Exponential(mean=2.0), cap=0)


def test_node_config_sink_has_no_successors():
    n = NodeConfig(id=1, service=Exponential(mean=2.0))
    assert n.is_sink()


def test_node_config_source_has_arrival():
    n = NodeConfig(id=1, service=Exponential(mean=2.0), arrival=Exponential(mean=1.0))
    assert n.is_source()


def test_entity_time_in_system_before_exit():
    e = Entity(id=1, entry_time=10.0, current_node=1)
    assert e.time_in_system is None


def test_entity_time_in_system_after_exit():
    e = Entity(id=1, entry_time=10.0, current_node=1)
    e.finalize(exit_time=25.0)
    assert e.time_in_system == 15.0


def test_entity_accumulates_wait_and_service():
    e = Entity(id=1, entry_time=0.0, current_node=1)
    e.register_wait(3.0)
    e.register_wait(1.5)
    e.register_service(4.0)
    assert e.total_wait_time == 4.5
    assert e.total_service_time == 4.0
