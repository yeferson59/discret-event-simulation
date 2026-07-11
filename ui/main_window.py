"""Ventana principal de la aplicación de escritorio: editor visual de la red,
configuración/ejecución de la simulación y reportes/gráficas, en tres
pestañas. Toda la lógica de negocio (parseo, motor, reportes, gráficas) vive
en `core`/`io_formats`/`viz`; esta capa solo arma widgets y los conecta.
"""

import json
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.engine import Engine
from core.stats import StatsCollector
from io_formats._shared import ParsedNetwork
from io_formats.def_parser import parse_def_file
from io_formats.def_writer import write_def_file
from io_formats.report_writer import (
    ReportConfig,
    format_summary_report,
    write_summary_report_file,
    write_trace_report_file,
)
from io_formats.xml_parser import parse_xml_file
from ui.editor_bridge import EditorBridge, network_to_json
from viz.plots import (
    plot_arrivals_vs_completions,
    plot_entity_times,
    plot_queue_sizes,
    plot_utilization,
)

EDITOR_HTML_PATH = Path(__file__).parent / "web" / "editor.html"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Simulador de Eventos Discretos")
        self.resize(1200, 800)

        self.bridge = EditorBridge()
        self.bridge.network_saved.connect(self._on_network_saved)
        self.stats: StatsCollector | None = None
        self._last_sim_time: float = 0.0

        tabs = QTabWidget()
        tabs.addTab(self._build_editor_tab(), "Editor visual")
        tabs.addTab(self._build_simulation_tab(), "Simulación")
        tabs.addTab(self._build_reports_tab(), "Reportes y gráficas")
        self._tabs = tabs
        self.setCentralWidget(tabs)

    # ---------------------------------------------------------------- #
    # Pestaña 1: editor visual
    # ---------------------------------------------------------------- #
    def _build_editor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        toolbar = QHBoxLayout()
        open_def_btn = QPushButton("Abrir .DEF...")
        open_xml_btn = QPushButton("Abrir .XML...")
        save_def_btn = QPushButton("Guardar .DEF...")
        open_def_btn.clicked.connect(self._open_def_file)
        open_xml_btn.clicked.connect(self._open_xml_file)
        save_def_btn.clicked.connect(self._save_def_file)
        toolbar.addWidget(open_def_btn)
        toolbar.addWidget(open_xml_btn)
        toolbar.addWidget(save_def_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.web_view = QWebEngineView()
        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self._channel)
        self.web_view.load(QUrl.fromLocalFile(str(EDITOR_HTML_PATH)))
        layout.addWidget(self.web_view)

        return widget

    def _open_def_file(self) -> None:
        self._open_network_file(parse_def_file, "Archivos .DEF (*.def)")

    def _open_xml_file(self) -> None:
        self._open_network_file(parse_xml_file, "Archivos XML (*.xml)")

    def _open_network_file(self, parser, name_filter: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir red", "", name_filter)
        if not path:
            return
        try:
            network = parser(path)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Error al abrir archivo", str(exc))
            return

        self.bridge.network = network
        self._push_network_to_editor(network)
        self._on_network_saved()

    def _push_network_to_editor(self, network: ParsedNetwork) -> None:
        payload_json = network_to_json(network)
        js_literal = json.dumps(payload_json)
        self.web_view.page().runJavaScript(f"window.loadNetworkFromPython({js_literal});")

    def _save_def_file(self) -> None:
        if self.bridge.network is None:
            QMessageBox.warning(
                self, "Sin red", 'Primero guardá una red con el botón "Guardar red" del editor visual.'
            )
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar .DEF", "red.def", "Archivos .DEF (*.def)")
        if not path:
            return
        write_def_file(self.bridge.network.nodes, self.bridge.network.sim_time, path)
        QMessageBox.information(self, "Guardado", f"Red escrita en {path}")

    def _on_network_saved(self) -> None:
        network = self.bridge.network
        if network is None:
            self._network_status_label.setText("Sin red cargada.")
            self._run_button.setEnabled(False)
            return

        self._network_status_label.setText(f"Red cargada: {len(network.nodes)} nodo(s).")
        self._sim_time_spin.setValue(network.sim_time)
        self._run_button.setEnabled(True)

    # ---------------------------------------------------------------- #
    # Pestaña 2: simulación
    # ---------------------------------------------------------------- #
    def _build_simulation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._network_status_label = QLabel("Sin red cargada.")
        layout.addWidget(self._network_status_label)

        form = QHBoxLayout()
        form.addWidget(QLabel("Tiempo de simulación:"))
        self._sim_time_spin = QDoubleSpinBox()
        self._sim_time_spin.setRange(0.01, 1_000_000.0)
        self._sim_time_spin.setDecimals(2)
        self._sim_time_spin.setValue(20.0)
        form.addWidget(self._sim_time_spin)

        self._seed_check = QCheckBox("Semilla fija:")
        form.addWidget(self._seed_check)
        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(0, 2_147_483_647)
        self._seed_spin.setValue(42)
        self._seed_spin.setEnabled(False)
        self._seed_check.toggled.connect(self._seed_spin.setEnabled)
        form.addWidget(self._seed_spin)
        form.addStretch()
        layout.addLayout(form)

        self._run_button = QPushButton("Ejecutar simulación")
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._run_simulation)
        layout.addWidget(self._run_button)

        self._run_status_label = QLabel("")
        layout.addWidget(self._run_status_label)
        layout.addStretch()

        return widget

    def _run_simulation(self) -> None:
        network = self.bridge.network
        if network is None:
            return

        sim_time = self._sim_time_spin.value()
        seed = self._seed_spin.value() if self._seed_check.isChecked() else None

        try:
            self.stats = Engine(network.nodes, sim_time=sim_time, seed=seed).run()
        except ValueError as exc:
            QMessageBox.critical(self, "Error al simular", str(exc))
            return

        self._last_sim_time = sim_time
        self._run_status_label.setText(f"Última corrida: sim_time={sim_time}, seed={seed}")
        self._refresh_reports_tab()
        self._tabs.setCurrentWidget(self._reports_tab_widget)

    # ---------------------------------------------------------------- #
    # Pestaña 3: reportes y gráficas
    # ---------------------------------------------------------------- #
    def _build_reports_tab(self) -> QWidget:
        widget = QWidget()
        self._reports_tab_widget = widget
        layout = QVBoxLayout(widget)

        options = QHBoxLayout()
        self._include_summary_check = QCheckBox("Resumen")
        self._include_summary_check.setChecked(True)
        self._include_per_node_check = QCheckBox("Por nodo")
        self._include_per_node_check.setChecked(True)
        self._include_trace_check = QCheckBox("Traza de eventos")
        self._trace_limit_spin = QSpinBox()
        self._trace_limit_spin.setRange(0, 1_000_000)
        self._trace_limit_spin.setSpecialValueText("(todos)")
        refresh_btn = QPushButton("Actualizar reporte")
        refresh_btn.clicked.connect(self._refresh_reports_tab)
        options.addWidget(self._include_summary_check)
        options.addWidget(self._include_per_node_check)
        options.addWidget(self._include_trace_check)
        options.addWidget(QLabel("Límite traza:"))
        options.addWidget(self._trace_limit_spin)
        options.addWidget(refresh_btn)
        options.addStretch()
        layout.addLayout(options)

        self._report_text = QTextEdit()
        self._report_text.setReadOnly(True)
        monospace_font = QFont()
        monospace_font.setFamilies(["Menlo", "Consolas", "monospace"])
        monospace_font.setStyleHint(QFont.StyleHint.Monospace)
        self._report_text.setCurrentFont(monospace_font)
        self._report_text.setMinimumHeight(180)

        report_panel = QWidget()
        report_layout = QVBoxLayout(report_panel)
        report_layout.setContentsMargins(0, 0, 0, 0)
        report_layout.addWidget(self._report_text)

        save_buttons = QHBoxLayout()
        save_report_btn = QPushButton("Guardar reporte...")
        save_report_btn.clicked.connect(self._save_report_file)
        save_trace_btn = QPushButton("Guardar traza...")
        save_trace_btn.clicked.connect(self._save_trace_file)
        save_buttons.addWidget(save_report_btn)
        save_buttons.addWidget(save_trace_btn)
        save_buttons.addStretch()
        report_layout.addLayout(save_buttons)

        plots_tabs = QTabWidget()
        self._queue_plot_layout = self._add_plot_tab(plots_tabs, "Colas")
        self._arrivals_plot_layout = self._add_plot_tab(plots_tabs, "Llegadas/Completadas")
        self._utilization_plot_layout = self._add_plot_tab(plots_tabs, "Utilización")
        self._entity_plot_layout = self._add_plot_tab(plots_tabs, "Tiempos por entidad")

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(report_panel)
        splitter.addWidget(plots_tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 540])
        layout.addWidget(splitter, stretch=1)

        return widget

    def _add_plot_tab(self, tabs: QTabWidget, title: str) -> QVBoxLayout:
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tabs.addTab(tab_widget, title)
        return tab_layout

    def _refresh_reports_tab(self) -> None:
        if self.stats is None:
            return

        config = ReportConfig(
            include_summary=self._include_summary_check.isChecked(),
            include_per_node=self._include_per_node_check.isChecked(),
            include_trace=self._include_trace_check.isChecked(),
            trace_limit=self._trace_limit_spin.value() or None,
        )
        self._report_text.setPlainText(
            format_summary_report(self.stats, self._last_sim_time, config)
        )

        self._set_plot(self._queue_plot_layout, plot_queue_sizes(self.stats))
        self._set_plot(self._arrivals_plot_layout, plot_arrivals_vs_completions(self.stats))
        self._set_plot(self._utilization_plot_layout, plot_utilization(self.stats))
        self._set_plot(self._entity_plot_layout, plot_entity_times(self.stats))

    def _set_plot(self, layout: QVBoxLayout, figure) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        layout.addWidget(FigureCanvasQTAgg(figure))

    def _save_report_file(self) -> None:
        if self.stats is None:
            QMessageBox.warning(self, "Sin datos", "Primero ejecutá una simulación.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar reporte", "reporte.txt", "Texto (*.txt)")
        if not path:
            return
        config = ReportConfig(
            include_summary=self._include_summary_check.isChecked(),
            include_per_node=self._include_per_node_check.isChecked(),
            include_trace=self._include_trace_check.isChecked(),
            trace_limit=self._trace_limit_spin.value() or None,
        )
        write_summary_report_file(self.stats, self._last_sim_time, path, config)
        QMessageBox.information(self, "Guardado", f"Reporte escrito en {path}")

    def _save_trace_file(self) -> None:
        if self.stats is None:
            QMessageBox.warning(self, "Sin datos", "Primero ejecutá una simulación.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar traza", "traza.txt", "Texto (*.txt)")
        if not path:
            return
        write_trace_report_file(self.stats, path)
        QMessageBox.information(self, "Guardado", f"Traza escrita en {path}")
