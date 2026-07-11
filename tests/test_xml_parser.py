import pytest

from core.distributions import Empirical, Exponential, Normal, Uniform
from core.engine import Engine
from io_formats.def_parser import parse_def_text
from io_formats.xml_parser import parse_xml_file, parse_xml_text


def test_parses_simple_network():
    xml = """
    <simulation sim_time="20" initial_clients="0">
      <node id="1" cap="1">
        <arrival kind="exp" mean="5.0"/>
        <service kind="exp" mean="2.0"/>
        <successors>
          <successor id="2" prob="1.0"/>
        </successors>
      </node>
      <node id="2" cap="1">
        <service kind="exp" mean="2.0"/>
      </node>
    </simulation>
    """
    parsed = parse_xml_text(xml)

    assert parsed.sim_time == 20.0
    assert parsed.initial_clients == 0
    assert len(parsed.nodes) == 2

    node1, node2 = parsed.nodes
    assert node1.id == 1
    assert isinstance(node1.arrival, Exponential) and node1.arrival.mean == 5.0
    assert isinstance(node1.service, Exponential) and node1.service.mean == 2.0
    assert node1.cap == 1
    assert node1.succ == [2]
    assert node1.prob == [1.0]

    assert node2.id == 2
    assert node2.arrival is None
    assert node2.is_sink()


def test_parses_extended_distribution_syntax():
    xml = """
    <simulation sim_time="10" initial_clients="0">
      <node id="1" cap="2">
        <arrival kind="uniform" a="1.0" b="10.0"/>
        <service kind="normal" mu="3.0" sigma="0.5"/>
      </node>
    </simulation>
    """
    parsed = parse_xml_text(xml)

    node = parsed.nodes[0]
    assert isinstance(node.arrival, Uniform)
    assert node.arrival.a == 1.0
    assert node.arrival.b == 10.0
    assert isinstance(node.service, Normal)
    assert node.service.mu == 3.0
    assert node.service.sigma == 0.5
    assert node.cap == 2


def test_parses_table_distribution():
    xml = """
    <simulation sim_time="10" initial_clients="0">
      <node id="1" cap="1">
        <arrival kind="exp" mean="4.0"/>
        <service kind="tabla">
          <value v="1.0" prob="0.3"/>
          <value v="2.0" prob="0.7"/>
          <value v="3.0" prob="1.0"/>
        </service>
      </node>
    </simulation>
    """
    parsed = parse_xml_text(xml)

    node = parsed.nodes[0]
    assert isinstance(node.service, Empirical)
    assert node.service.values == [1.0, 2.0, 3.0]
    assert node.service.cum_probs == [0.3, 0.7, 1.0]


def test_parses_sink_node_without_successors_element():
    xml = """
    <simulation sim_time="10" initial_clients="0">
      <node id="1" cap="1">
        <service kind="exp" mean="2.0"/>
      </node>
    </simulation>
    """
    node = parse_xml_text(xml).nodes[0]
    assert node.succ == []
    assert node.prob == []
    assert node.is_sink()


def test_parses_sink_node_with_empty_successors_element():
    xml = """
    <simulation sim_time="10" initial_clients="0">
      <node id="1" cap="1">
        <service kind="exp" mean="2.0"/>
        <successors/>
      </node>
    </simulation>
    """
    node = parse_xml_text(xml).nodes[0]
    assert node.succ == []
    assert node.prob == []
    assert node.is_sink()


def test_node_cap_defaults_to_one_when_omitted():
    xml = """
    <simulation sim_time="10" initial_clients="0">
      <node id="1">
        <service kind="exp" mean="2.0"/>
      </node>
    </simulation>
    """
    node = parse_xml_text(xml).nodes[0]
    assert node.cap == 1


def test_rejects_nonzero_initial_clients():
    xml = '<simulation sim_time="10" initial_clients="3"><node id="1"><service kind="exp" mean="1.0"/></node></simulation>'
    with pytest.raises(ValueError):
        parse_xml_text(xml)


def test_rejects_missing_service_element():
    xml = '<simulation sim_time="10" initial_clients="0"><node id="1"/></simulation>'
    with pytest.raises(ValueError):
        parse_xml_text(xml)


def test_rejects_unknown_distribution_kind():
    xml = '<simulation sim_time="10" initial_clients="0"><node id="1"><service kind="poisson" mean="1.0"/></node></simulation>'
    with pytest.raises(ValueError):
        parse_xml_text(xml)


def test_rejects_missing_distribution_param():
    xml = '<simulation sim_time="10" initial_clients="0"><node id="1"><service kind="uniform" a="1.0"/></node></simulation>'
    with pytest.raises(ValueError):
        parse_xml_text(xml)


def test_rejects_malformed_xml():
    with pytest.raises(ValueError):
        parse_xml_text("<simulation sim_time='10'>")


def test_rejects_wrong_root_tag():
    xml = '<network sim_time="10" initial_clients="0"></network>'
    with pytest.raises(ValueError):
        parse_xml_text(xml)


def test_parsed_network_feeds_directly_into_engine():
    xml = """
    <simulation sim_time="20" initial_clients="0">
      <node id="1" cap="1">
        <arrival kind="exp" mean="4.0"/>
        <service kind="exp" mean="1.0"/>
        <successors>
          <successor id="2" prob="1.0"/>
        </successors>
      </node>
      <node id="2" cap="1">
        <service kind="exp" mean="2.0"/>
      </node>
    </simulation>
    """
    parsed = parse_xml_text(xml)
    stats = Engine(parsed.nodes, sim_time=parsed.sim_time, seed=42).run()

    summary = stats.summary(sim_time=parsed.sim_time)
    assert summary.entities_created > 0


def test_parse_xml_file_reads_from_disk(tmp_path):
    xml = '<simulation sim_time="15" initial_clients="0"><node id="1" cap="1"><arrival kind="exp" mean="3.0"/><service kind="exp" mean="1.0"/></node></simulation>'
    xml_file = tmp_path / "network.xml"
    xml_file.write_text(xml, encoding="utf-8")

    parsed = parse_xml_file(xml_file)

    assert parsed.sim_time == 15.0
    assert len(parsed.nodes) == 1
    assert isinstance(parsed.nodes[0].arrival, Exponential)


def test_def_and_xml_parsers_produce_equivalent_networks():
    def_text = "\n".join(
        [
            "20 0",
            "1",
            "uniform:1.0,10.0 normal:3.0,0.5 2",
            "1",
            "2",
            "1.0",
            "2",
            "exp:2.0 1",
            "0",
            "",
            "",
        ]
    )
    xml_text = """
    <simulation sim_time="20" initial_clients="0">
      <node id="1" cap="2">
        <arrival kind="uniform" a="1.0" b="10.0"/>
        <service kind="normal" mu="3.0" sigma="0.5"/>
        <successors>
          <successor id="2" prob="1.0"/>
        </successors>
      </node>
      <node id="2" cap="1">
        <service kind="exp" mean="2.0"/>
      </node>
    </simulation>
    """

    from_def = parse_def_text(def_text)
    from_xml = parse_xml_text(xml_text)

    assert from_def.sim_time == from_xml.sim_time
    assert len(from_def.nodes) == len(from_xml.nodes)

    for node_def, node_xml in zip(from_def.nodes, from_xml.nodes):
        assert node_def.id == node_xml.id
        assert node_def.cap == node_xml.cap
        assert node_def.succ == node_xml.succ
        assert node_def.prob == node_xml.prob
        assert type(node_def.service) is type(node_xml.service)
        assert node_def.service == node_xml.service
        assert type(node_def.arrival) is type(node_xml.arrival)
        assert node_def.arrival == node_xml.arrival
