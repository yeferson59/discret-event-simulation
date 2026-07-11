from core.distributions import (
    Empirical,
    Exponential,
    Normal,
    Uniform,
)
from core.models import NodeConfig
from io_formats.xml_parser import parse_xml_text
from io_formats.xml_writer import format_xml_text, write_xml_file


def test_format_xml_text_writes_root_attributes():
    node = NodeConfig(id=1, service=Exponential(mean=2.0))
    text = format_xml_text([node], sim_time=20)

    root_line = text.splitlines()[1]
    assert 'sim_time="20"' in root_line
    assert 'initial_clients="0"' in root_line


def test_format_xml_text_writes_arrival_and_service_elements():
    node = NodeConfig(id=1, service=Exponential(mean=2.0), arrival=Exponential(mean=5.0))
    text = format_xml_text([node], sim_time=20)

    assert '<arrival kind="exp" mean="5.0"/>' in text
    assert '<service kind="exp" mean="2.0"/>' in text


def test_format_xml_text_omits_arrival_element_when_none():
    node = NodeConfig(id=1, service=Exponential(mean=1.0))
    text = format_xml_text([node], sim_time=10)

    assert "<arrival" not in text


def test_format_xml_text_writes_extended_distribution_params():
    node = NodeConfig(id=1, service=Normal(mu=3.0, sigma=0.5), cap=2)
    text = format_xml_text([node], sim_time=10)

    assert '<service kind="normal" mu="3.0" sigma="0.5"/>' in text


def test_format_xml_text_encodes_table_distribution():
    node = NodeConfig(
        id=1, service=Empirical(values=[1.0, 2.0], cum_probs=[0.4, 1.0])
    )
    text = format_xml_text([node], sim_time=10)

    assert '<service kind="tabla">' in text
    assert '<value v="1.0" prob="0.4"/>' in text
    assert '<value v="2.0" prob="1.0"/>' in text


def test_format_xml_text_writes_successors():
    node = NodeConfig(
        id=1, service=Exponential(mean=1.0), succ=[2, 3], prob=[0.5, 1.0]
    )
    text = format_xml_text([node], sim_time=10)

    assert '<successor id="2" prob="0.5"/>' in text
    assert '<successor id="3" prob="1.0"/>' in text


def test_format_xml_text_omits_successors_element_for_sink_node():
    node = NodeConfig(id=1, service=Exponential(mean=1.0))
    text = format_xml_text([node], sim_time=10)

    assert "<successors" not in text


def test_round_trips_through_xml_parser():
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

    text = format_xml_text(nodes, sim_time=42.0)
    parsed = parse_xml_text(text)

    assert parsed.sim_time == 42.0
    assert parsed.initial_clients == 0
    assert parsed.nodes == nodes


def test_write_xml_file_writes_expected_contents(tmp_path):
    node = NodeConfig(id=1, service=Exponential(mean=1.0))
    expected = format_xml_text([node], sim_time=10)

    out_file = tmp_path / "network.xml"
    write_xml_file([node], sim_time=10, path=out_file)

    assert out_file.read_text(encoding="utf-8") == expected
