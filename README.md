# Discret Event Simulation (DES)

Aplicación de escritorio (PySide6) para simular redes de procesos por eventos
discretos, con soporte para múltiples distribuciones de tiempo de servicio,
trazas de eventos, estadísticas globales y visualización gráfica de la red.

## Structure Project

```
core/         Modelo de datos y motor de simulación (sin dependencias de UI/IO)
  models.py         NodeConfig, Entity
  distributions.py  Exponential, Uniform, Triangular, Normal, Empirical,
                     TriangularInverse, LogNormal, Beta, Gamma, Weibull, Pareto
                     (todas sobre random de la stdlib: una corrida con seed
                     fija es reproducible de punta a punta)
  engine.py         Motor DES con heapq (servidores en paralelo por nodo, parada por sim_time)
  stats.py          Colector de series por nodo (colas, utilización), traza cruda de
                     eventos, series de llegadas/completadas del sistema y resumen por entidad

io_formats/   Lectura/escritura de archivos
  def_parser.py     Parser .DEF con auto-detección de dos variantes: el
                     formato extendido de este proyecto (id explícito por
                     bloque) y el formato legado del profesor (tipo de nodo
                     1/2, ids implícitos 1..N, sinks sin líneas de
                     sucesores, CRLF — ej. Red2.def). Los campos tLL/ts
                     aceptan un número suelto (exponencial, retrocompatible)
                     o `kind:params` para cualquier distribución de
                     core/distributions.py. Produce
                     ParsedNetwork(nodes, sim_time, initial_clients).
  def_writer.py     Inverso de def_parser.py: list[NodeConfig] -> texto .DEF
                     (probado con round-trip contra def_parser). Usado por el
                     editor visual para cumplir la funcionalidad #1.
  xml_parser.py     Parser XML equivalente en información al .DEF (mismo
                     ParsedNetwork). Esquema: <simulation><node><arrival/>
                     <service/><successors/></node></simulation>.
  report_writer.py  Reporte de texto configurable (secciones activables vía
                     ReportConfig) y archivo de traza de eventos, ambos leídos
                     directamente de StatsCollector
  _shared.py        ParsedNetwork, mapeo de parámetros por distribución y
                     dump_distribution() (inverso de Distribution.from_spec),
                     compartido entre parsers y writers

viz/          Gráficas (matplotlib embebido en Qt)
  plots.py          Figures matplotlib puras (sin pyplot ni plt.show()), listas
                     para embeber en FigureCanvasQTAgg: tamaño de cola por nodo
                     superpuesto, llegadas vs. completadas acumuladas,
                     utilización por nodo y tiempos globales por entidad con
                     sus promedios

ui/           Interfaz de escritorio
  main_window.py    Ventana principal PySide6: 3 pestañas (editor visual,
                     configuración/ejecución de la simulación, reportes y
                     gráficas). Delega toda la lógica a core/io_formats/viz.
  editor_bridge.py  QObject expuesto vía QWebChannel como `bridge`: recibe
                     la red armada en el editor (JSON), la valida
                     construyendo NodeConfig/Distribution reales, y sabe
                     serializar de vuelta (network_to_json) para precargar
                     el editor al abrir un archivo.
  web/editor.html   Editor visual con Cytoscape.js (construido desde cero:
                     no existía el notebook heredado en este repo para
                     "portarlo casi intacto" como sugería la idea original).
                     Canvas para la topología + panel de formulario por nodo
                     (distribución de llegada/servicio) + botón que llama a
                     bridge vía QWebChannel.
  web/vendor/       cytoscape.min.js vendorizado (MIT) para que el editor
                     funcione sin conexión a internet en tiempo de ejecución.

tests/        Pruebas con pytest (core/, io_formats/, viz/ — ver nota sobre ui/ abajo)
```

`core/` no debe importar nada de `ui/`, `io_formats/` ni `viz/`. Todo parser de
entrada produce una lista de `NodeConfig`; toda capa de salida consume los
resultados del motor. Esto permite probar el motor de simulación sin levantar
la interfaz gráfica.

## How Can You Run Tests?

```bash
uv sync
uv run pytest tests/ -v
```

## Cómo correr la app (macOS)

```bash
uv run python main.py
```

Si al lanzarla ves `qt.qpa.plugin: Could not find the Qt platform plugin
"cocoa" in ""`, es porque `uv` marca `.venv/` con el flag de macOS
`UF_HIDDEN` (para ocultarlo de Finder), y Qt (a diferencia de Python)
respeta ese flag al enumerar directorios: ve la carpeta de plugins como
vacía aunque los archivos estén ahí. Se arregla así (metadata únicamente,
no toca el contenido de `.venv/`):

```bash
chflags -R nohidden .venv
```

Hay que repetirlo si borrás y recreás `.venv` desde cero (`uv venv --clear`
o borrar la carpeta a mano) — `uv` vuelve a poner el flag en la creación.

## Current State

- [x] Modelo de datos (`NodeConfig`, `Entity`)
- [x] Distribuciones (exponencial, uniforme, triangular, triangular inversa,
      normal, lognormal, beta, gamma, weibull, pareto, tabla)
- [x] Motor DES generalizado (heapq + entidades + traza de eventos + series de
      cola/llegadas/completadas)
- [x] Parser .DEF extendido (retrocompatible, con distribuciones y validación)
- [x] Parser XML (mismo contrato ParsedNetwork/list[NodeConfig] que el .DEF)
- [x] Reporte de texto configurable + archivo de traza de eventos
- [x] Gráficas (colas, llegadas/completadas, utilización, tiempos globales)
- [x] Interfaz PySide6 + editor visual (Cytoscape.js vía QWebEngineView).
      El editor es código nuevo, no un port literal del notebook heredado
      (no estaba disponible en este repo). No verificado interactivamente
      todavía — ver nota abajo.
- [ ] Empaquetado (PyInstaller) para macOS y Windows

### Nota sobre `ui/`

`ui/` no tiene tests automatizados: `QWebEngineView` no es viable de testear
con pytest headless en este entorno (falta un plugin de plataforma Qt
funcional para correr sin pantalla). Se verificó en su lugar que:

- todos los módulos de `ui/` importan sin errores y `MainWindow` expone los
  métodos esperados;
- `EditorBridge` (parseo/serialización JSON <-> `ParsedNetwork`) se probó
  directamente, incluido un round-trip completo;
- el JS de `editor.html` pasa `node --check` (sin errores de sintaxis).

Falta la verificación real, interactiva, de la ventana (`uv run python
main.py`, crear nodos, conectar sucesores, guardar `.DEF`, correr una
simulación y revisar reportes/gráficas) — no se pudo lanzar una ventana real
de Qt en el entorno donde se escribió este código.
