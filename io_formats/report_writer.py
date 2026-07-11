"""Reporte de texto configurable (#4) y archivo de traza de eventos (#5),
generados a partir de lo que ya emite `core.stats.StatsCollector`.

Sigue el mismo patrón que los parsers: una función `format_*` que produce un
string (fácil de testear sin tocar disco) y una función `write_*_file` que
solo agrega la escritura a disco encima.
"""

from dataclasses import dataclass
from pathlib import Path

from core.stats import StatsCollector


@dataclass
class ReportConfig:
    """Controla qué secciones incluye el reporte de texto (#4): el mismo
    `StatsCollector` puede reportarse distinto según lo que necesite el
    modelo (ej. omitir la traza si la corrida fue muy larga)."""

    title: str = "Reporte de simulación"
    decimals: int = 2
    include_summary: bool = True
    include_per_node: bool = True
    include_trace: bool = False
    trace_limit: int | None = None


def format_summary_report(
    stats: StatsCollector, sim_time: float, config: ReportConfig | None = None
) -> str:
    """Genera el reporte de texto configurable (#4): resumen global,
    estadísticas por nodo y, opcionalmente, la traza de eventos embebida."""
    config = config or ReportConfig()
    lines: list[str] = [f"=== {config.title} ==="]

    if config.include_summary:
        lines.extend(_format_summary_section(stats, sim_time, config.decimals))

    if config.include_per_node:
        lines.append("")
        lines.extend(_format_per_node_section(stats, config.decimals))

    if config.include_trace:
        lines.append("")
        lines.extend(_format_trace_lines(stats, config.trace_limit))

    return "\n".join(lines) + "\n"


def format_trace_report(stats: StatsCollector) -> str:
    """Genera el archivo de traza de eventos (#5): una línea por evento
    `(tiempo, nodo, tipo, entidad)`, en el mismo orden cronológico en que el
    motor los emitió."""
    rows = [
        f"t={r.time:.4f}\tnodo={r.node_id}\ttipo={r.event_type.value}\tentidad={r.entity_id}"
        for r in stats.trace
    ]
    return "\n".join(rows) + ("\n" if rows else "")


def write_report_file(text: str, path: str | Path) -> None:
    """Escribe a disco un reporte ya generado por `format_summary_report` o
    `format_trace_report`."""
    Path(path).write_text(text, encoding="utf-8")


def write_summary_report_file(
    stats: StatsCollector,
    sim_time: float,
    path: str | Path,
    config: ReportConfig | None = None,
) -> None:
    write_report_file(format_summary_report(stats, sim_time, config), path)


def write_trace_report_file(stats: StatsCollector, path: str | Path) -> None:
    write_report_file(format_trace_report(stats), path)


def _format_summary_section(
    stats: StatsCollector, sim_time: float, decimals: int
) -> list[str]:
    summary = stats.summary(sim_time)
    return [
        f"Tiempo de simulación: {_fmt(summary.sim_time, decimals)}",
        f"Entidades creadas: {summary.entities_created}",
        f"Entidades completadas: {summary.entities_completed}",
        f"Tiempo promedio en sistema: {_fmt(summary.avg_time_in_system, decimals)}",
        f"Tiempo promedio de espera: {_fmt(summary.avg_wait_time, decimals)}",
        f"Tiempo promedio de servicio: {_fmt(summary.avg_service_time, decimals)}",
    ]


def _format_per_node_section(stats: StatsCollector, decimals: int) -> list[str]:
    lines = [
        "--- Estadísticas por nodo ---",
        f"{'Nodo':<6}{'Llegadas':<10}{'Completadas':<13}{'Cola prom.':<12}{'Utilización':<12}",
    ]
    for node_id in sorted(stats.node_stats):
        ns = stats.node_stats[node_id]
        util_pct = _fmt(ns.utilization * 100, decimals) + "%"
        lines.append(
            f"{node_id:<6}{ns.arrivals:<10}{ns.completions:<13}"
            f"{_fmt(ns.avg_queue_length, decimals):<12}{util_pct:<12}"
        )
    return lines


def _format_trace_lines(stats: StatsCollector, limit: int | None) -> list[str]:
    lines = ["--- Traza de eventos ---"]
    records = stats.trace if limit is None else stats.trace[:limit]

    for record in records:
        lines.append(
            f"t={record.time:.2f}  nodo={record.node_id}  "
            f"{record.event_type.value:<16}entidad={record.entity_id}"
        )

    omitted = len(stats.trace) - len(records)
    if omitted > 0:
        lines.append(f"... ({omitted} eventos más omitidos)")

    return lines


def _fmt(value: float | None, decimals: int) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"
