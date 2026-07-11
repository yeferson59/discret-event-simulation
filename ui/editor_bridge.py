"""Puente `QWebChannel` entre el editor visual (`ui/web/editor.html`,
Cytoscape.js) y Python. Reemplaza a `google.colab.output.register_callback`
del notebook heredado: el JS de la página llama a un slot de este `QObject`
en vez de invocar una función registrada en el kernel de Colab.

`EditorBridge` no sabe nada de Qt más allá de `QObject`/`Signal`/`Slot`: la
validación real (construir `NodeConfig`/`Distribution`) se delega por
completo a `core`, así que un JSON inválido o una red inconsistente se
rechaza con el mismo `ValueError` que ya usan los parsers de `io_formats`.
"""

import json

from PySide6.QtCore import QObject, Signal, Slot

from core.distributions import Distribution
from core.models import NodeConfig
from io_formats._shared import ParsedNetwork, dump_distribution


class EditorBridge(QObject):
    """Expuesto a JS como `bridge` vía `QWebChannel.registerObject`."""

    network_saved = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.network: ParsedNetwork | None = None

    @Slot(str, result=str)
    def save_network(self, json_str: str) -> str:
        """Recibe la red armada en el editor (JSON), la valida y la guarda
        en memoria. Devuelve `""` si quedó guardada, o un mensaje de error
        legible en caso contrario (JS lo usa para avisarle al usuario)."""
        try:
            network = self._parse_network(json_str)
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            return f"Red inválida: {exc}"

        self.network = network
        self.network_saved.emit()
        return ""

    def _parse_network(self, json_str: str) -> ParsedNetwork:
        payload = json.loads(json_str)
        nodes = [self._parse_node(node_data) for node_data in payload["nodes"]]
        return ParsedNetwork(
            nodes=nodes, sim_time=float(payload["sim_time"]), initial_clients=0
        )

    def _parse_node(self, data: dict) -> NodeConfig:
        arrival_data = data.get("arrival")
        return NodeConfig(
            id=int(data["id"]),
            service=self._parse_distribution(data["service"]),
            cap=int(data["cap"]),
            arrival=self._parse_distribution(arrival_data) if arrival_data else None,
            succ=[int(s) for s in data["succ"]],
            prob=[float(p) for p in data["prob"]],
        )

    def _parse_distribution(self, data: dict) -> Distribution:
        return Distribution.from_spec(data["kind"], data["params"])


def network_to_json(network: ParsedNetwork) -> str:
    """Serializa una `ParsedNetwork` al mismo JSON que produce
    `buildNetworkPayload()` en `editor.html`, para que `MainWindow` pueda
    empujarla de vuelta al editor visual (ej. tras abrir un `.DEF`/`.XML`)
    llamando a `window.loadNetworkFromPython`."""
    return json.dumps(
        {
            "sim_time": network.sim_time,
            "nodes": [_node_to_dict(node) for node in network.nodes],
        }
    )


def _node_to_dict(node: NodeConfig) -> dict:
    return {
        "id": node.id,
        "cap": node.cap,
        "arrival": _distribution_to_dict(node.arrival) if node.arrival else None,
        "service": _distribution_to_dict(node.service),
        "succ": node.succ,
        "prob": node.prob,
    }


def _distribution_to_dict(dist: Distribution) -> dict:
    kind, params = dump_distribution(dist)
    return {"kind": kind, "params": params}
