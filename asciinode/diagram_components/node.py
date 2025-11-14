from typing import List, Optional, Tuple, TYPE_CHECKING

from .core import Position
from ..errors import DiagramError

if TYPE_CHECKING:
    from .diagram import Diagram


class Node:

    def __init__(self, text: str, parent: Optional["Node"] = None) -> None:
        self.text = text
        self.parent = parent
        self.children: List[Tuple["Node", Position]] = []
        self.position_from_parent: Optional[Position] = None
        self.diagram: Optional["Diagram"] = parent.diagram if parent else None

        self.x = 0
        self.y = 0
        self.width = 0
        self.lines: List[str] = [text]
        self.height = 3
        self.box_width = len(text) + 4
        self.subtree_height = self.height
        self.subtree_min_x = 0
        self.subtree_max_x = self.box_width
        self.subtree_width = self.box_width
        self.branch_row_index = 0
        self.branch_anchor_y: Optional[int] = None
        self.branch_from: Optional[Position] = None
        self.tokens_lines: List[List[Tuple[str, str, int]]] = []

    def add(self, text: str, position: Position = Position.BOTTOM) -> "Node":
        child = Node(text, parent=self)
        child.position_from_parent = position
        child.diagram = self.diagram
        self.children.append((child, position))
        return child

    def add_bottom(self, text: str) -> "Node":
        return self.add(text, Position.BOTTOM)

    def add_right(self, text: str) -> "Node":
        return self.add(text, Position.RIGHT)

    def add_left(self, text: str) -> "Node":
        return self.add(text, Position.LEFT)

    def add_top(self, text: str) -> "Node":
        return self.add(text, Position.TOP)

    def link(self, other: "Node", **edge_kwargs):
        if not self.diagram:
            raise DiagramError(
                "Node belum terhubung dengan Diagram, panggil melalui Diagram.connect()."
            )
        return self.diagram.connect(self, other, **edge_kwargs)
