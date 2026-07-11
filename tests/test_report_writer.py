from core.distributions import Uniform
from core.engine import Engine
from core.models import NodeConfig
from core.stats import StatsCollector
from io_formats.report_writer import (
    ReportConfig,
    format_summary_report,
    format_trace_report,
    write_summary_report_file,
    write_trace_report_file,
)


def const(value: float) -> Uniform:
    """Distribución determinística: Uniform(a, a) siempre devuelve `a`."""
    return Uniform(a=value, b=value)


def run_simple_network():
    node = NodeConfig(id=1, service=const(2.0), arrival=const(5.0), cap=1)
    return Engine([node], sim_time=20).run()


def test_format_summary_report_includes_global_and_per_node_sections():
    stats = run_simple_network()
    report = format_summary_report(stats, sim_time=20)

    assert "Entidades creadas: 4" in report
    assert "Entidades completadas: 3" in report
    assert "Tiempo promedio en sistema: 2.00" in report
    assert "--- Estadísticas por nodo ---" in report
    assert "1     4         3" in report


def test_format_summary_report_respects_include_flags():
    stats = run_simple_network()

    no_per_node = format_summary_report(
        stats, sim_time=20, config=ReportConfig(include_per_node=False)
    )
    assert "--- Estadísticas por nodo ---" not in no_per_node
    assert "Entidades creadas" in no_per_node

    no_summary = format_summary_report(
        stats, sim_time=20, config=ReportConfig(include_summary=False)
    )
    assert "Entidades creadas" not in no_summary
    assert "--- Estadísticas por nodo ---" in no_summary


def test_format_summary_report_uses_na_when_no_entity_completed():
    node = NodeConfig(id=1, service=const(100.0), arrival=const(0.5), cap=1)
    stats = Engine([node], sim_time=1).run()

    report = format_summary_report(stats, sim_time=1)

    assert "Entidades completadas: 0" in report
    assert "Tiempo promedio en sistema: N/A" in report


def test_format_summary_report_can_embed_trace():
    stats = run_simple_network()
    report = format_summary_report(
        stats, sim_time=20, config=ReportConfig(include_trace=True)
    )

    assert "--- Traza de eventos ---" in report
    assert "llegada" in report
    assert "entidad=1" in report


def test_format_summary_report_trace_limit_notes_omitted_count():
    stats = run_simple_network()
    total_events = len(stats.trace)
    assert total_events > 2

    report = format_summary_report(
        stats,
        sim_time=20,
        config=ReportConfig(include_trace=True, trace_limit=2),
    )

    assert f"({total_events - 2} eventos más omitidos)" in report


def test_format_trace_report_lists_all_events_chronologically():
    stats = run_simple_network()
    report = format_trace_report(stats)

    trace_lines = report.splitlines()
    assert len(trace_lines) == len(stats.trace)
    assert trace_lines[0].startswith("t=5.0000")
    assert "tipo=llegada" in trace_lines[0]

    times = [float(line.split("\t")[0].removeprefix("t=")) for line in trace_lines]
    assert times == sorted(times)


def test_format_trace_report_is_empty_string_when_no_events():
    node = NodeConfig(id=1, service=const(1.0))
    stats = StatsCollector([node])

    assert format_trace_report(stats) == ""


def test_write_summary_report_file_writes_expected_contents(tmp_path):
    stats = run_simple_network()
    expected = format_summary_report(stats, sim_time=20)

    out_file = tmp_path / "report.txt"
    write_summary_report_file(stats, sim_time=20, path=out_file)

    assert out_file.read_text(encoding="utf-8") == expected


def test_write_trace_report_file_writes_expected_contents(tmp_path):
    stats = run_simple_network()
    expected = format_trace_report(stats)

    out_file = tmp_path / "trace.txt"
    write_trace_report_file(stats, path=out_file)

    assert out_file.read_text(encoding="utf-8") == expected
