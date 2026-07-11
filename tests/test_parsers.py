import pytest

from core.distributions import (
    Empirical,
    Exponential,
    Normal,
    Uniform,
)
from core.engine import Engine
from io_formats.def_parser import parse_def_file, parse_def_text


def lines(*rows: str) -> str:
    return "\n".join(rows)


def test_parses_simple_backward_compatible_def():
    text = lines(
        "20 0",
        "1",
        "5.0 2.0 1",
        "1",
        "2",
        "1.0",
        "2",
        "2.0 1",
        "0",
        "",
        "",
    )
    parsed = parse_def_text(text)

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
    assert isinstance(node2.service, Exponential) and node2.service.mean == 2.0
    assert node2.cap == 1
    assert node2.is_sink()


def test_parses_extended_distribution_syntax():
    text = lines(
        "10 0",
        "1",
        "uniform:1.0,10.0 normal:3.0,0.5 2",
        "0",
        "",
        "",
    )
    parsed = parse_def_text(text)

    node = parsed.nodes[0]
    assert isinstance(node.arrival, Uniform)
    assert node.arrival.a == 1.0
    assert node.arrival.b == 10.0
    assert isinstance(node.service, Normal)
    assert node.service.mu == 3.0
    assert node.service.sigma == 0.5
    assert node.cap == 2


def test_parses_table_distribution():
    text = lines(
        "10 0",
        "1",
        "exp:4.0 tabla:1.0:0.3;2.0:0.7;3.0:1.0 1",
        "0",
        "",
        "",
    )
    parsed = parse_def_text(text)

    node = parsed.nodes[0]
    assert isinstance(node.service, Empirical)
    assert node.service.values == [1.0, 2.0, 3.0]
    assert node.service.cum_probs == [0.3, 0.7, 1.0]


def test_parses_sink_node_with_blank_successor_lines():
    text = lines(
        "10 0",
        "1",
        "2.0 1",
        "0",
        "",
        "",
    )
    parsed = parse_def_text(text)

    node = parsed.nodes[0]
    assert node.succ == []
    assert node.prob == []
    assert node.is_sink()


def test_rejects_nonzero_initial_clients():
    text = lines("10 3", "1", "2.0 1", "0", "", "")
    with pytest.raises(ValueError):
        parse_def_text(text)


def test_rejects_mismatched_successor_count():
    text = lines(
        "10 0",
        "1",
        "2.0 1",
        "2",
        "2",
        "1.0",
    )
    with pytest.raises(ValueError):
        parse_def_text(text)


def test_rejects_unknown_distribution_kind():
    text = lines("10 0", "1", "poisson:1.0 2.0 1", "0", "", "")
    with pytest.raises(ValueError):
        parse_def_text(text)


def test_rejects_malformed_service_line():
    text = lines("10 0", "1", "1.0 2.0 3.0 4.0", "0", "", "")
    with pytest.raises(ValueError):
        parse_def_text(text)


def test_parsed_network_feeds_directly_into_engine():
    text = lines(
        "20 0",
        "1",
        "exp:4.0 exp:1.0 1",
        "1",
        "2",
        "1.0",
        "2",
        "exp:2.0 1",
        "0",
        "",
        "",
    )
    parsed = parse_def_text(text)

    stats = Engine(parsed.nodes, sim_time=parsed.sim_time, seed=42).run()

    summary = stats.summary(sim_time=parsed.sim_time)
    assert summary.entities_created > 0


# Contenido real de un .DEF entregado por el profesor (Red2.def): sin línea
# de id por nodo (la primera línea de cada bloque es el tipo: 1=con llegadas,
# 2=sin), ids implícitos 1..N, sinks sin líneas de sucesores, y CRLF.
LEGACY_RED2 = (
    "1000.0 0 \r\n"
    "1 \r\n"
    "3.0 1.0 1 \r\n"
    "3 \r\n"
    "2 3 4 \r\n"
    "0.5 0.7 1.0 \r\n"
    "1 \r\n"
    "3.0 1.0 1 \r\n"
    "2 \r\n"
    "1 4 \r\n"
    "0.5 1.0 \r\n"
    "2 \r\n"
    "0.5 1 \r\n"
    "1 \r\n"
    "5 \r\n"
    "1.0 \r\n"
    "2 \r\n"
    "0.5 1 \r\n"
    "1 \r\n"
    "5 \r\n"
    "1.0 \r\n"
    "2 \r\n"
    "0.2 1\r\n"
    "0"
)


def test_parses_legacy_professor_format_with_implicit_ids():
    parsed = parse_def_text(LEGACY_RED2)

    assert parsed.sim_time == 1000.0
    assert [n.id for n in parsed.nodes] == [1, 2, 3, 4, 5]

    node1, node2, node3, node4, node5 = parsed.nodes
    assert isinstance(node1.arrival, Exponential) and node1.arrival.mean == 3.0
    assert node1.succ == [2, 3, 4] and node1.prob == [0.5, 0.7, 1.0]
    assert isinstance(node2.arrival, Exponential) and node2.arrival.mean == 3.0
    assert node2.succ == [1, 4] and node2.prob == [0.5, 1.0]
    assert node3.arrival is None and node3.succ == [5]
    assert node4.arrival is None and node4.succ == [5]
    assert node5.arrival is None and node5.is_sink()
    assert node5.service.mean == 0.2


def test_legacy_network_feeds_directly_into_engine():
    parsed = parse_def_text(LEGACY_RED2)
    stats = Engine(parsed.nodes, sim_time=parsed.sim_time, seed=42).run()
    summary = stats.summary(sim_time=parsed.sim_time)
    assert summary.entities_created > 0
    assert summary.entities_completed > 0


def test_legacy_midfile_sink_omits_successor_lines():
    # En el formato legado un sink en medio del archivo no deja líneas de
    # ids/probabilidades: el bloque siguiente empieza inmediatamente.
    text = lines(
        "10 0",
        "1",
        "3.0 1.0 1",
        "1",
        "2",
        "1.0",
        "2",  # nodo 2: tipo 2...
        "0.5 1",
        "0",  # ...sink: sin líneas de sucesores
        "2",  # nodo 3: tipo 2
        "0.5 1",
        "0",
    )
    parsed = parse_def_text(text)

    assert [n.id for n in parsed.nodes] == [1, 2, 3]
    assert parsed.nodes[1].is_sink()
    assert parsed.nodes[2].is_sink()


def test_rejects_duplicate_node_ids_in_extended_format():
    # Ids duplicados con un tipo que no puede ser legado (arrival en un
    # bloque cuyo "tipo" sería 2): debe fallar en ambos formatos.
    text = lines(
        "10 0",
        "2",
        "3.0 1.0 1",
        "0",
        "",
        "",
        "2",
        "2.0 1",
        "0",
        "",
        "",
    )
    with pytest.raises(ValueError):
        parse_def_text(text)


def test_parse_def_file_reads_from_disk(tmp_path):
    text = lines("15 0", "1", "3.0 1.0 1", "0", "", "")
    def_file = tmp_path / "network.def"
    def_file.write_text(text, encoding="utf-8")

    parsed = parse_def_file(def_file)

    assert parsed.sim_time == 15.0
    assert len(parsed.nodes) == 1
    assert isinstance(parsed.nodes[0].arrival, Exponential)
