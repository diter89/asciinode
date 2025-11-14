from dataclasses import dataclass
from typing import Optional

from .node import Node


@dataclass
class Edge:
    source: Node
    target: Node
    label: Optional[str] = None
    bidirectional: bool = False
    style: Optional[str] = None
