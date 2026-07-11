"""Gráficas matplotlib construidas a partir de las series que ya emite
`core.stats.StatsCollector`.

Cada función recibe un `StatsCollector` (y, cuando aplica, el `sim_time` de
la corrida) y devuelve una `matplotlib.figure.Figure` sin llamar a
`plt.show()` ni depender de `pyplot`: así se puede embeber directamente en
`FigureCanvasQTAgg` (ui/), guardar a disco o testear sin levantar ninguna
interfaz gráfica. `viz/` no debe importar de `ui/`.
"""

from matplotlib.axes import Axes
from matplotlib.figure import Figure

from core.stats import StatsCollector

# Paleta oscura consistente con el resto de la UI (ver ui/web/editor.html:
# toolbar #23272e, botones #2f333b) para que las gráficas embebidas no
# contrasten con fondo blanco contra el resto de la ventana en modo oscuro.
_FIG_BG = "#2b2f36"
_AXES_BG = "#23272e"
_FG = "#e6e6e6"
_GRID = "#3a3f49"


def _new_figure() -> tuple[Figure, Axes]:
    # layout="constrained" recalcula márgenes automáticamente para que
    # título/labels/leyenda no se recorten ni se encimen con los datos,
    # incluso cuando el widget del canvas se redimensiona.
    fig = Figure(layout="constrained")
    fig.set_facecolor(_FIG_BG)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_AXES_BG)
    ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(_GRID)
    ax.tick_params(colors=_FG)
    ax.xaxis.label.set_color(_FG)
    ax.yaxis.label.set_color(_FG)
    ax.title.set_color(_FG)
    return fig, ax


def _style_legend(legend) -> None:
    if legend is None:
        return
    frame = legend.get_frame()
    frame.set_facecolor(_AXES_BG)
    frame.set_edgecolor(_GRID)
    for text in legend.get_texts():
        text.set_color(_FG)


def plot_queue_sizes(stats: StatsCollector) -> Figure:
    """Tamaño de cola por nodo a lo largo del tiempo, superpuestos en una
    sola gráfica (funcionalidad #6)."""
    fig, ax = _new_figure()

    for node_id in sorted(stats.node_stats):
        history = stats.node_stats[node_id].history
        if not history:
            continue
        times = [snap.time for snap in history]
        queue_lengths = [snap.queue_length for snap in history]
        ax.step(times, queue_lengths, where="post", label=f"Nodo {node_id}")

    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Tamaño de cola")
    ax.set_title("Tamaño de cola por nodo")
    if ax.lines:
        _style_legend(ax.legend())

    return fig


def plot_arrivals_vs_completions(stats: StatsCollector) -> Figure:
    """Entidades que llegaron al sistema vs. las que fueron atendidas,
    acumuladas en el tiempo (funcionalidad #7)."""
    fig, ax = _new_figure()

    if stats.system_arrivals:
        times, counts = zip(*stats.system_arrivals)
        ax.step(times, counts, where="post", label="Llegadas")
    if stats.system_completions:
        times, counts = zip(*stats.system_completions)
        ax.step(times, counts, where="post", label="Completadas")

    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Entidades acumuladas")
    ax.set_title("Llegadas vs. entidades atendidas")
    if ax.lines:
        _style_legend(ax.legend())

    return fig


def plot_utilization(stats: StatsCollector) -> Figure:
    """Utilización del recurso de cada nodo (funcionalidad #8): fracción del
    tiempo total de simulación en que sus servidores estuvieron ocupados."""
    fig, ax = _new_figure()

    node_ids = sorted(stats.node_stats)
    utilizations = [stats.node_stats[nid].utilization * 100 for nid in node_ids]

    ax.bar([str(nid) for nid in node_ids], utilizations, color="#3462eb")
    ax.set_xlabel("Nodo")
    ax.set_ylabel("Utilización (%)")
    ax.set_title("Utilización del recurso por nodo")
    ax.set_ylim(0, 100)

    return fig


def plot_entity_times(stats: StatsCollector) -> Figure:
    """Estadísticas globales por entidad (funcionalidad #9): tiempo en el
    sistema, tiempo en cola total y tiempo de servicio total de cada entidad
    completada, con sus promedios marcados como líneas horizontales."""
    fig, ax = _new_figure()
    ax.set_xlabel("Entidad")
    ax.set_ylabel("Tiempo")
    ax.set_title("Tiempos globales por entidad")

    completed = sorted(
        (e for e in stats.entities.values() if e.exit_time is not None),
        key=lambda e: e.id,
    )
    if not completed:
        return fig

    entity_ids = [e.id for e in completed]
    time_in_system = [e.time_in_system for e in completed]
    wait_time = [e.total_wait_time for e in completed]
    service_time = [e.total_service_time for e in completed]

    # Con pocas entidades una línea ayuda a seguir la secuencia; con muchas,
    # las líneas entre cientos de puntos no relacionados solo generan ruido
    # visual, así que se muestran como dispersión.
    many_entities = len(completed) > 60
    scatter_kwargs = {"s": 10, "alpha": 0.5, "linewidths": 0} if many_entities else {
        "s": 20, "alpha": 0.8, "linewidths": 0
    }
    ax.scatter(entity_ids, time_in_system, label="Tiempo en sistema", color="C0", **scatter_kwargs)
    ax.scatter(entity_ids, wait_time, label="Tiempo en cola", color="C1", **scatter_kwargs)
    ax.scatter(entity_ids, service_time, label="Tiempo de servicio", color="C2", **scatter_kwargs)
    if not many_entities:
        ax.plot(entity_ids, time_in_system, color="C0", alpha=0.4, linewidth=1)
        ax.plot(entity_ids, wait_time, color="C1", alpha=0.4, linewidth=1)
        ax.plot(entity_ids, service_time, color="C2", alpha=0.4, linewidth=1)

    ax.axhline(
        sum(time_in_system) / len(time_in_system),
        linestyle="--",
        color="C0",
        label="Promedio en sistema",
    )
    ax.axhline(
        sum(wait_time) / len(wait_time),
        linestyle="--",
        color="C1",
        label="Promedio en cola",
    )
    ax.axhline(
        sum(service_time) / len(service_time),
        linestyle="--",
        color="C2",
        label="Promedio de servicio",
    )

    handles, labels = ax.get_legend_handles_labels()
    _style_legend(fig.legend(handles, labels, loc="outside right upper"))

    return fig
