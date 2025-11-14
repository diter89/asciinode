from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from ..diagram_components.core import Position


_POSITION_ALIASES: Dict[str, Position] = {
    "top": Position.TOP,
    "bottom": Position.BOTTOM,
    "left": Position.LEFT,
    "right": Position.RIGHT,
}


def _coerce_position(value: Optional[str]) -> Position:
    if not value:
        return Position.BOTTOM
    return _POSITION_ALIASES.get(value.lower(), Position.BOTTOM)


@dataclass
class NodeInstruction:
    node_id: str
    text: str
    parent_id: Optional[str] = None
    position: Position = Position.BOTTOM

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "NodeInstruction":
        if "id" not in payload or "text" not in payload:
            raise ValueError("Node instruction must include 'id' and 'text'.")
        node_id = str(payload["id"])
        text = str(payload["text"])
        parent_id = payload.get("parent")
        if parent_id is not None:
            parent_id = str(parent_id)
        position = _coerce_position(str(payload.get("position", "")))
        return cls(node_id=node_id, text=text, parent_id=parent_id, position=position)


@dataclass
class EdgeInstruction:
    source_id: str
    target_id: str
    label: Optional[str] = None
    style: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "EdgeInstruction":
        if "source" not in payload or "target" not in payload:
            raise ValueError("Edge instruction must include 'source' and 'target'.")
        source = str(payload["source"])
        target = str(payload["target"])
        label = payload.get("label")
        if label is not None:
            label = str(label)
        style = payload.get("style")
        if style is not None:
            style = str(style)
        return cls(source_id=source, target_id=target, label=label, style=style)


@dataclass
class DiagramInstruction:
    nodes: List[NodeInstruction] = field(default_factory=list)
    edges: List[EdgeInstruction] = field(default_factory=list)
    title: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "DiagramInstruction":
        nodes_payload = payload.get("nodes")
        edges_payload = payload.get("edges")

        if not isinstance(nodes_payload, Iterable):
            raise ValueError("Diagram instruction must include iterable 'nodes'.")

        nodes = [NodeInstruction.from_dict(node) for node in nodes_payload]

        edges: List[EdgeInstruction] = []
        if isinstance(edges_payload, Iterable):
            edges = [EdgeInstruction.from_dict(edge) for edge in edges_payload]

        title = payload.get("title")
        if title is not None:
            title = str(title)

        return cls(nodes=nodes, edges=edges, title=title)
