from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .diagram import Diagram
from .node import Node


@dataclass
class DiffResult:
    added_nodes: List[str]
    removed_nodes: List[str]
    changed_nodes: List[Tuple[str, str, str]]
    added_edges: List[Tuple[str, str]]
    removed_edges: List[Tuple[str, str]]

    def has_changes(self) -> bool:
        return any(
            [
                self.added_nodes,
                self.removed_nodes,
                self.changed_nodes,
                self.added_edges,
                self.removed_edges,
            ]
        )


def _walk_nodes(
    node: Node, path: Tuple[int, ...], mapping: Dict[Tuple[int, ...], Node]
):
    mapping[path] = node
    for index, (child, _) in enumerate(node.children):
        _walk_nodes(child, path + (index,), mapping)


def _walk_edges(diagram: Diagram) -> Iterable[Tuple[Node, Node]]:
    for edge in diagram._edges:
        yield edge.source, edge.target


def diff(diagram_a: Diagram, diagram_b: Diagram) -> DiffResult:
    mapping_a: Dict[Tuple[int, ...], Node] = {}
    mapping_b: Dict[Tuple[int, ...], Node] = {}

    _walk_nodes(diagram_a.root, (), mapping_a)
    _walk_nodes(diagram_b.root, (), mapping_b)

    added_nodes: List[str] = []
    removed_nodes: List[str] = []
    changed_nodes: List[Tuple[str, str, str]] = []

    all_keys = set(mapping_a.keys()).union(mapping_b.keys())
    for key in sorted(all_keys):
        node_a = mapping_a.get(key)
        node_b = mapping_b.get(key)
        identifier = "->".join(str(idx) for idx in key) or "root"
        if node_a is None and node_b is not None:
            added_nodes.append(identifier)
        elif node_b is None and node_a is not None:
            removed_nodes.append(identifier)
        elif node_a and node_b and node_a.text != node_b.text:
            changed_nodes.append((identifier, node_a.text, node_b.text))

    def edge_key(source: Node, target: Node) -> Tuple[str, str, str]:
        return (
            getattr(source, "text", ""),
            getattr(target, "text", ""),
            f"{id(source)}->{id(target)}",
        )

    edges_a = {edge_key(src, dst) for src, dst in _walk_edges(diagram_a)}
    edges_b = {edge_key(src, dst) for src, dst in _walk_edges(diagram_b)}

    added_edges = sorted(edges_b - edges_a)
    removed_edges = sorted(edges_a - edges_b)

    return DiffResult(
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        changed_nodes=changed_nodes,
        added_edges=[(src, dst) for src, dst, _ in added_edges],
        removed_edges=[(src, dst) for src, dst, _ in removed_edges],
    )
