from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from .core import Position, Shape
from ..errors import DiagramError

if TYPE_CHECKING:
    from .diagram import Diagram


class Node:
    def __init__(
        self, text: str, parent: Optional["Node"] = None, shape: Shape = Shape.RECTANGLE
    ) -> None:
        self.text = text
        self.original_text = text
        self.parent = parent
        self.children: List[Tuple["Node", Position]] = []
        self.position_from_parent: Optional[Position] = None
        self.title: Optional[str] = None
        self.title_tokens: List[Tuple[str, str, int]] = []
        self.diagram: Optional["Diagram"] = parent.diagram if parent else None
        self.diagram: Optional["Diagram"] = parent.diagram if parent else None
        self.shape = shape

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
        self.llm_enabled = False
        self.llm_query: Optional[str] = None
        self.llm_response: Optional[str] = None
        self.llm_system_prompt: Optional[str] = None

    def add(
        self,
        text: str,
        position: Position = Position.BOTTOM,
        *,
        title: Optional[str] = None,
        shape: Shape = Shape.RECTANGLE,
        llm_answer: bool = False,
        llm_query: Optional[str] = None,
        llm_kwargs: Optional[Dict[str, object]] = None,
        llm_system_prompt: Optional[str] = None,
    ) -> "Node":
        child = Node(text, parent=self, shape=shape)
        child.position_from_parent = position
        child.title = title
        child.diagram = self.diagram

        if llm_answer:
            if not self.diagram:
                raise DiagramError(
                    "Node is not connected to a Diagram, cannot retrieve LLM answer."
                )
            query = llm_query or text
            response = self.diagram._resolve_llm_answer(
                query,
                llm_kwargs or {},
                llm_system_prompt=llm_system_prompt,
            )
            child.llm_enabled = True
            child.llm_query = query
            child.llm_response = response
            child.llm_system_prompt = llm_system_prompt
            child.text = response
            response_lines = response.splitlines() or [response]
            child.lines = response_lines
        else:
            child.llm_enabled = False
            child.llm_query = None
            child.llm_response = None
            child.llm_system_prompt = None

        self.children.append((child, position))
        return child

    def add_bottom(self, text: str, **kwargs) -> "Node":
        return self.add(text, Position.BOTTOM, **kwargs)

    def add_right(self, text: str, **kwargs) -> "Node":
        return self.add(text, Position.RIGHT, **kwargs)

    def add_left(self, text: str, **kwargs) -> "Node":
        return self.add(text, Position.LEFT, **kwargs)

    def add_top(self, text: str, **kwargs) -> "Node":
        return self.add(text, Position.TOP, **kwargs)

    def add_llm_answer(
        self,
        query: str,
        position: Position = Position.BOTTOM,
        **kwargs,
    ) -> "Node":
        kwargs.setdefault("llm_answer", True)
        kwargs.setdefault("llm_query", query)
        return self.add(query, position, **kwargs)

    def link(self, other: "Node", **edge_kwargs):
        if not self.diagram:
            raise DiagramError(
                "Node is not connected to a Diagram, call through Diagram.connect()."
            )
        return self.diagram.connect(self, other, **edge_kwargs)
