from core.distributions import (
    Empirical,
    Exponential,
    Normal,
    Uniform,
)
from core.models import NodeConfig
from io_formats.def_parser import parse_def_text
from io_formats.def_writer import format_def_text, write_def_file


def test_format_def_text_uses_bare_number_for_exponential():
    node = NodeConfig(id=1, service=Exponential(mean=2.0), arrival=Exponential(mean=5.0))
    text = format_def_text([node], sim_time=20)

    lines = text.splitlines()
    assert lines[0] == "20 0"
    assert lines[1] == "1"
    assert lines[2] == "5.0 2.0 1"


def test_format_def_text_uses_kind_prefix_for_extended_distributions():
    node = NodeConfig(id=1, service=Normal(mu=3.0, sigma=0.5), cap=2)
    text = format_def_text([node], sim_time=10)

    assert "normal:3.0,0.5 2" in text


def test_format_def_text_encodes_table_distribution():
    node = NodeConfig(
        id=1, service=Empirical(values=[1.0, 2.0], cum_probs=[0.4, 1.0])
    )
    text = format_def_text([node], sim_time=10)

    assert "tabla:1.0:0.4;2.0:1.0" in text


def test_format_def_text_writes_successors_and_probabilities():
    node = NodeConfig(
        id=1, service=Exponential(mean=1.0), succ=[2, 3], prob=[0.5, 1.0]
    )
    text = format_def_text([node], sim_time=10)

    lines = text.splitlines()
    assert lines[3] == "2"
    assert lines[4] == "2 3"
    assert lines[5] == "0.5 1.0"


def test_format_def_text_writes_blank_lines_for_sink_node():
    node = NodeConfig(id=1, service=Exponential(mean=1.0))
    text = format_def_text([node], sim_time=10)

    lines = text.splitlines()
    assert lines[3] == "0"
    assert lines[4] == ""
    assert lines[5] == ""


def test_format_def_text_omits_arrival_field_when_none():
    node = NodeConfig(id=1, service=Exponential(mean=1.0), cap=3)
    text = format_def_text([node], sim_time=10)

    assert "1.0 3" in text.splitlines()


def test_round_trips_through_def_parser():
    nodes = [
        NodeConfig(
            id=1,
            service=Uniform(a=1.0, b=10.0),
            arrival=Exponential(mean=4.0),
            cap=2,
            succ=[2, 3],
            prob=[0.6, 1.0],
        ),
        NodeConfig(id=2, service=Normal(mu=3.0, sigma=0.5), succ=[3], prob=[1.0]),
        NodeConfig(
            id=3, service=Empirical(values=[1.0, 5.0], cum_probs=[0.3, 1.0])
        ),
    ]

    text = format_def_text(nodes, sim_time=42.0)
    parsed = parse_def_text(text)

    assert parsed.sim_time == 42.0
    assert parsed.initial_clients == 0
    assert parsed.nodes == nodes


def test_write_def_file_writes_expected_contents(tmp_path):
    node = NodeConfig(id=1, service=Exponential(mean=1.0))
    expected = format_def_text([node], sim_time=10)

    out_file = tmp_path / "network.def"
    write_def_file([node], sim_time=10, path=out_file)

    assert out_file.read_text(encoding="utf-8") == expected
