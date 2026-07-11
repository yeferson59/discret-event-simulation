from matplotlib.figure import Figure

from core.distributions import Uniform
from core.engine import Engine
from core.models import NodeConfig
from core.stats import StatsCollector
from viz.plots import (
    plot_arrivals_vs_completions,
    plot_entity_times,
    plot_queue_sizes,
    plot_utilization,
)


def const(value: float) -> Uniform:
    """Distribución determinística: Uniform(a, a) siempre devuelve `a`."""
    return Uniform(a=value, b=value)


def run_two_node_network():
    node1 = NodeConfig(
        id=1, service=const(2.0), arrival=const(3.0), cap=1, succ=[2], prob=[1.0]
    )
    node2 = NodeConfig(id=2, service=const(1.0), cap=1)
    return Engine([node1, node2], sim_time=20).run()


def empty_stats():
    node = NodeConfig(id=1, service=const(1.0))
    return StatsCollector([node])


def test_plot_queue_sizes_returns_one_line_per_node_with_history():
    stats = run_two_node_network()
    fig = plot_queue_sizes(stats)

    assert isinstance(fig, Figure)
    ax = fig.axes[0]
    assert len(ax.lines) == 2
    assert {line.get_label() for line in ax.lines} == {"Nodo 1", "Nodo 2"}


def test_plot_queue_sizes_handles_nodes_with_no_history():
    fig = plot_queue_sizes(empty_stats())

    ax = fig.axes[0]
    assert len(ax.lines) == 0


def test_plot_arrivals_vs_completions_plots_two_series():
    stats = run_two_node_network()
    fig = plot_arrivals_vs_completions(stats)

    ax = fig.axes[0]
    labels = {line.get_label() for line in ax.lines}
    assert labels == {"Llegadas", "Completadas"}

    arrivals_line = next(l for l in ax.lines if l.get_label() == "Llegadas")
    assert list(arrivals_line.get_ydata()) == [1, 2, 3, 4, 5, 6]


def test_plot_arrivals_vs_completions_handles_no_data():
    fig = plot_arrivals_vs_completions(empty_stats())

    ax = fig.axes[0]
    assert len(ax.lines) == 0


def test_plot_utilization_has_one_bar_per_node_within_valid_range():
    stats = run_two_node_network()
    fig = plot_utilization(stats)

    ax = fig.axes[0]
    bars = ax.patches
    assert len(bars) == 2
    for bar in bars:
        assert 0.0 <= bar.get_height() <= 100.0


def test_plot_utilization_handles_node_with_no_activity():
    fig = plot_utilization(empty_stats())

    ax = fig.axes[0]
    assert len(ax.patches) == 1
    assert ax.patches[0].get_height() == 0.0


def test_plot_entity_times_plots_series_and_average_lines():
    stats = run_two_node_network()
    fig = plot_entity_times(stats)

    ax = fig.axes[0]
    _, labels = ax.get_legend_handles_labels()
    assert set(labels) == {
        "Tiempo en sistema",
        "Tiempo en cola",
        "Tiempo de servicio",
        "Promedio en sistema",
        "Promedio en cola",
        "Promedio de servicio",
    }

    time_in_system_scatter = next(
        c for c in ax.collections if c.get_label() == "Tiempo en sistema"
    )
    completed = [e for e in stats.entities.values() if e.exit_time is not None]
    assert len(time_in_system_scatter.get_offsets()) == len(completed)


def test_plot_entity_times_handles_no_completed_entities():
    fig = plot_entity_times(empty_stats())

    ax = fig.axes[0]
    assert len(ax.lines) == 0
