import heapq
import shutil
from collections import deque, defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

from wcwidth import wcwidth

from ..errors import ConfigurationError, DiagramError, LayoutOverflowError
from .canvas import Canvas
from .core import BoxChars, Position
from .grid_layout import GridLayout
from .edge import Edge
from .node import Node


class Diagram:

    def __init__(
        self,
        root_text: str,
        max_box_width: Optional[int] = 36,
        max_layout_width: Optional[int] = 80,
        allow_intersections: bool = False,
        vertical_spacing: int = 4,
        horizontal_spacing: int = 4,
        canvas_width: Optional[int] = None,
        canvas_height: Optional[int] = None,
        connector_style: Optional[str] = None,
        box_style: Optional[Union[str, BoxChars]] = None,
    ):
        if not isinstance(root_text, str):
            raise ConfigurationError("root_text must be a string.")

        for name, value in (
            ("vertical_spacing", vertical_spacing),
            ("horizontal_spacing", horizontal_spacing),
            ("canvas_width", canvas_width),
            ("canvas_height", canvas_height),
        ):
            if value is not None and not isinstance(value, int):
                raise ConfigurationError(f"{name} must be an integer.")

        if connector_style is not None and not isinstance(connector_style, str):
            raise ConfigurationError("connector_style must be a string when provided.")

        self.root = Node(root_text)

        if isinstance(box_style, BoxChars):
            self.chars = box_style
        else:
            style_key = box_style or "rounded"
            if not isinstance(style_key, str):
                raise ConfigurationError("box_style must be a string or BoxChars instance.")
            try:
                self.chars = BoxChars.for_style(style_key)
            except ValueError as exc:
                raise ConfigurationError(str(exc)) from exc
        self.v_spacing = max(1, vertical_spacing)
        self.h_spacing = max(1, horizontal_spacing)
        self.max_box_width = max_box_width
        self.max_layout_width = max_layout_width
        self._current_layout_width = max_layout_width
        self._effective_max_box_width = max_box_width
        if not isinstance(allow_intersections, bool):
            raise ConfigurationError("allow_intersections must be a boolean value.")
        self.allow_intersections = allow_intersections
        self._canvas_width_config = canvas_width
        self._canvas_height_config = canvas_height
        if canvas_width is not None and canvas_width < 32:
            raise ConfigurationError("canvas_width must be at least 32 characters when specified.")
        if canvas_height is not None and canvas_height < 32:
            raise ConfigurationError("canvas_height must be at least 32 characters when specified.")
        self.canvas_width = max(32, canvas_width) if canvas_width is not None else 200
        self.canvas_height = max(32, canvas_height) if canvas_height is not None else 1000
        self._edges: List[Edge] = []
        self._edge_state: Dict[Tuple[int, int], Dict[str, object]] = {}
        self.connector_style = connector_style
        self._manual_layout: Optional[Tuple[str, object]] = None
        self._grid_min_nodes = 8

        if max_box_width is not None and max_box_width < 10:
            raise ConfigurationError("max_box_width must be at least 10 characters.")
        if max_layout_width is not None and max_layout_width < 24:
            raise ConfigurationError("max_layout_width must be at least 24 characters.")
        if (
            max_box_width is not None
            and max_layout_width is not None
            and max_layout_width < max_box_width
        ):
            raise ConfigurationError("max_layout_width must be greater than or equal to max_box_width.")
        self.root.diagram = self

    def _prepare_node(self, node: Node):
        content_limit = None
        effective_width = self._effective_max_box_width or self.max_box_width
        if effective_width:
            content_limit = max(effective_width - 4, 1)

        tokens = self._tokenize_markup(node.text or "")
        lines_tokens = self._wrap_tokens(tokens, content_limit)
        if not lines_tokens:
            lines_tokens = [[("text", " ", 1)]]

        plain_lines: List[str] = []
        display_widths: List[int] = []
        for line in lines_tokens:
            plain_chars = [value for kind, value, _ in line if kind == "text"]
            plain_lines.append("".join(plain_chars).rstrip())
            display_widths.append(sum(token[2] for token in line if token[0] == "text"))

        inner_width = max(display_widths) if display_widths else 0
        node.lines = plain_lines
        node.tokens_lines = lines_tokens
        node.box_width = inner_width + 4
        if effective_width:
            node.box_width = min(node.box_width, effective_width)
        node.height = len(lines_tokens) + 2
        node.subtree_height = node.height
        node.subtree_min_x = 0
        node.subtree_max_x = node.box_width
        node.subtree_width = node.box_width

    def _prepare_nodes(self, node: Node):
        self._prepare_node(node)
        for child, _ in node.children:
            self._prepare_nodes(child)

    def _tokenize_markup(self, text: str) -> List[Tuple[str, str, int]]:
        tokens: List[Tuple[str, str, int]] = []
        i = 0
        length = len(text)
        while i < length:
            char = text[i]
            if char == "[":
                end = text.find("]", i + 1)
                if end != -1:
                    tag = text[i : end + 1]
                    tokens.append(("tag", tag, 0))
                    i = end + 1
                    continue
            if char == "\n":
                tokens.append(("newline", char, 0))
            else:
                tokens.append(("text", char, max(wcwidth(char), 1)))
            i += 1
        return tokens

    def _wrap_tokens(self, tokens: List[Tuple[str, str, int]], limit: Optional[int]) -> List[List[Tuple[str, str, int]]]:
        if not tokens:
            return [[]]

        def closing_for(tag: str) -> str:
            if tag.startswith("[") and not tag.startswith("[/"):
                return f"[/{tag[1:]}"
            return tag

        lines: List[List[Tuple[str, str, int]]] = []
        current: List[Tuple[str, str, int]] = []
        line_width = 0
        active_tags: List[str] = []

        def close_active(line: List[Tuple[str, str, int]]):
            for tag in reversed(active_tags):
                line.append(("tag", closing_for(tag), 0))

        def start_new_line():
            nonlocal current, line_width
            if current:
                close_active(current)
                lines.append(current)
            current = []
            line_width = 0
            for tag in active_tags:
                current.append(("tag", tag, 0))

        def ensure_limit(width: int):
            nonlocal line_width
            if limit and limit > 0 and line_width + width > limit and current:
                start_new_line()

        for kind, value, width in tokens:
            if kind == "newline":
                start_new_line()
                continue

            if kind == "tag":
                if value.startswith("[/"):
                    current.append((kind, value, width))
                    target = value[2:-1]
                    if active_tags and active_tags[-1][1:-1] == target:
                        active_tags.pop()
                    else:
                        for idx in range(len(active_tags) - 1, -1, -1):
                            if active_tags[idx][1:-1] == target:
                                active_tags.pop(idx)
                                break
                else:
                    active_tags.append(value)
                    current.append((kind, value, width))
                continue

            ensure_limit(width)
            current.append(("text", value, width))
            line_width += width

        if current:
            close_active(current)
            lines.append(current)

        return lines or [[]]

    def _group_bottom_children(self, children: List[Node]) -> List[List[Node]]:
        if not children:
            return []
        limit = self._current_layout_width
        if not limit:
            return [children]

        rows: List[List[Node]] = []
        current_row: List[Node] = []
        current_width = 0

        for child in children:
            child_width = child.subtree_width
            additional = child_width if not current_row else self.h_spacing + child_width
            if current_row and current_width + additional > limit:
                rows.append(current_row)
                current_row = [child]
                current_width = child_width
            else:
                if current_row:
                    current_width += self.h_spacing + child_width
                else:
                    current_width = child_width
                current_row.append(child)

        if current_row:
            rows.append(current_row)

        return rows

    def _char_to_dirs(self, char: str) -> set:
        mapping = {
            " ": set(),
            self.chars.vertical: {"up", "down"},
            self.chars.horizontal: {"left", "right"},
            self.chars.top_left: {"down", "right"},
            self.chars.top_right: {"down", "left"},
            self.chars.bottom_left: {"up", "right"},
            self.chars.bottom_right: {"up", "left"},
            self.chars.cross: {"up", "down", "left", "right"},
            self.chars.tee_up: {"up", "left", "right"},
            self.chars.tee_down: {"down", "left", "right"},
            self.chars.tee_left: {"up", "down", "left"},
            self.chars.tee_right: {"up", "down", "right"},
            "┌": {"down", "right"},
            "┐": {"down", "left"},
            "└": {"up", "right"},
            "┘": {"up", "left"},
            "┼": {"up", "down", "left", "right"},
            "┴": {"up", "left", "right"},
            "┬": {"down", "left", "right"},
            "├": {"up", "down", "right"},
            "┤": {"up", "down", "left"},
        }
        return set(mapping.get(char, set()))

    def _dirs_to_char(self, dirs: set) -> str:
        if not dirs:
            return " "
        key = frozenset(dirs)
        mapping = {
            frozenset({"up", "down"}): self.chars.vertical,
            frozenset({"left", "right"}): self.chars.horizontal,
            frozenset({"down", "right"}): self.chars.top_left,
            frozenset({"down", "left"}): self.chars.top_right,
            frozenset({"up", "right"}): self.chars.bottom_left,
            frozenset({"up", "left"}): self.chars.bottom_right,
            frozenset({"up", "down", "left", "right"}): self.chars.cross,
            frozenset({"up", "left", "right"}): self.chars.tee_up,
            frozenset({"down", "left", "right"}): self.chars.tee_down,
            frozenset({"up", "down", "left"}): self.chars.tee_left,
            frozenset({"up", "down", "right"}): self.chars.tee_right,
            frozenset({"up"}): self.chars.vertical,
            frozenset({"down"}): self.chars.vertical,
            frozenset({"left"}): self.chars.horizontal,
            frozenset({"right"}): self.chars.horizontal,
        }
        return mapping.get(key, self.chars.cross)

    def _write_dirs(self, canvas: Canvas, x: int, y: int, dirs: set, style: Optional[str] = None):
        if style is None:
            style = self.connector_style
        existing_dirs = self._char_to_dirs(canvas.get(x, y))
        combined = existing_dirs.union(dirs)
        self._set_connector_char(canvas, x, y, self._dirs_to_char(combined), style)

    def _measure_subtree(self, node: Node):
        if not node.children:
            node.subtree_min_x = 0
            node.subtree_max_x = node.box_width
            node.subtree_width = node.box_width
            return

        child_extents = []
        for child, position in node.children:
            self._measure_subtree(child)
            child_extents.append((child, position))

        min_x = 0
        max_x = node.box_width
        node.subtree_height = node.height

        right_children = [child for child, pos in child_extents if pos == Position.RIGHT]
        left_children = [child for child, pos in child_extents if pos == Position.LEFT]
        bottom_children = [child for child, pos in child_extents if pos == Position.BOTTOM]
        top_children = [child for child, pos in child_extents if pos == Position.TOP]

        for child in left_children:
            child_min = child.subtree_min_x
            child_max = child.subtree_max_x
            child_x = -self.h_spacing - child_max
            min_x = min(min_x, child_x + child_min)
            max_x = max(max_x, child_x + child_max)

        for child in right_children:
            child_min = child.subtree_min_x
            child_max = child.subtree_max_x
            child_x = node.box_width + self.h_spacing - child_min
            min_x = min(min_x, child_x + child_min)
            max_x = max(max_x, child_x + child_max)

        if bottom_children:
            row_groups = self._group_bottom_children(bottom_children)
            current_y = node.height + self.v_spacing
            max_extent = node.height

            for row in row_groups:
                row_width = sum(child.subtree_width for child in row) + self.h_spacing * (len(row) - 1)
                start_x = node.box_width // 2 - row_width // 2
                current_x = start_x
                for child in row:
                    child_min = child.subtree_min_x
                    child_max = child.subtree_max_x
                    child_x = current_x - child_min
                    min_x = min(min_x, child_x + child_min)
                    max_x = max(max_x, child_x + child_max)
                    current_x += child.subtree_width + self.h_spacing

                row_height = max(child.subtree_height for child in row)
                max_extent = max(max_extent, current_y + row_height)
                current_y += row_height + self.v_spacing

            node.subtree_height = max(node.subtree_height, max_extent)

        if top_children:
            row_groups = self._group_bottom_children(top_children)
            for row in row_groups:
                row_width = sum(child.subtree_width for child in row) + self.h_spacing * (len(row) - 1)
                start_x = node.box_width // 2 - row_width // 2
                current_x = start_x
                for child in row:
                    child_min = child.subtree_min_x
                    child_max = child.subtree_max_x
                    child_x = current_x - child_min
                    min_x = min(min_x, child_x + child_min)
                    max_x = max(max_x, child_x + child_max)
                    current_x += child.subtree_width + self.h_spacing

        if right_children:
            offset = 0
            max_span = node.height
            for child in right_children:
                max_span = max(max_span, offset + child.subtree_height)
                offset += child.subtree_height + self.v_spacing
            node.subtree_height = max(node.subtree_height, max_span)

        if left_children:
            offset = 0
            max_span = node.height
            for child in left_children:
                max_span = max(max_span, offset + child.subtree_height)
                offset += child.subtree_height + self.v_spacing
            node.subtree_height = max(node.subtree_height, max_span)

        node.subtree_min_x = min_x
        node.subtree_max_x = max_x
        node.subtree_width = max_x - min_x

    def add(self, text: str, position: Position = Position.BOTTOM) -> Node:
        return self.root.add(text, position)

    def add_bottom(self, text: str) -> Node:
        return self.root.add_bottom(text)

    def add_right(self, text: str) -> Node:
        return self.root.add_right(text)

    def add_left(self, text: str) -> Node:
        return self.root.add_left(text)

    def add_top(self, text: str) -> Node:
        return self.root.add_top(text)

    def connect(
        self,
        source: Node,
        target: Node,
        *,
        label: Optional[str] = None,
        bidirectional: bool = False,
        style: Optional[str] = None,
    ) -> Edge:
        if not isinstance(source, Node) or not isinstance(target, Node):
            raise DiagramError("source dan target harus berupa Node.")
        if source.diagram is not self or target.diagram is not self:
            raise DiagramError("Node tidak berasal dari diagram ini.")
        if style is None:
            style = self.connector_style
        edge = Edge(source=source, target=target, label=label, bidirectional=bidirectional, style=style)
        self._edges.append(edge)
        return edge

    def clear_edges(self) -> None:
        self._edges.clear()

    def _calculate_layout(self):
        self._effective_max_box_width = self.max_box_width

        layout_limit = self._current_layout_width
        attempts = 0
        while True:
            self._prepare_nodes(self.root)
            self._measure_subtree(self.root)

            if self._manual_layout:
                layout_type, payload = self._manual_layout
                if layout_type == "grid":
                    grid_rows = payload
                    GridLayout(
                        self,
                        grid_rows,
                        horizontal_spacing=self.h_spacing,
                        vertical_spacing=self.v_spacing,
                    ).apply()
                    return

            if not layout_limit or self.root.subtree_width <= layout_limit or not self._effective_max_box_width:
                break
            if self._effective_max_box_width <= 14:
                break
            self._effective_max_box_width = max(14, self._effective_max_box_width - 4)
            attempts += 1
            if attempts > 10:
                break

        self.root.x = 0
        self.root.y = 0
        total_nodes = self._count_nodes(self.root)
        use_grid_layout = self._manual_layout is None and self._should_use_grid_layout(self.root, total_nodes, True)
        if use_grid_layout:
            self._layout_grid(self.root)
        else:
            self._layout_node(self.root)
        if not self.allow_intersections and not use_grid_layout:
            self._auto_avoid()

    def _count_nodes(self, node: Node) -> int:
        total = 1
        for child, _ in node.children:
            total += self._count_nodes(child)
        return total

    def _should_use_grid_layout(self, node: Node, total_nodes: int, is_root: bool) -> bool:
        if not node.children:
            return True
        if is_root and total_nodes <= self._grid_min_nodes:
            return False
        for child, position in node.children:
            if position is not Position.BOTTOM:
                return False
            if not self._should_use_grid_layout(child, total_nodes, False):
                return False
        return True

    def use_grid_layout(self, rows: List[List[Node]]) -> None:
        if not rows:
            raise ConfigurationError("Grid layout requires at least one row.")
        row_length = len(rows[0])
        if row_length == 0:
            raise ConfigurationError("Grid layout rows must not be empty.")
        seen: Set[Node] = set()
        normalized: List[List[Node]] = []
        for row in rows:
            if len(row) != row_length:
                raise ConfigurationError("All grid rows must have the same length.")
            normalized_row: List[Node] = []
            for node in row:
                if not isinstance(node, Node):
                    raise ConfigurationError("Grid layout entries must be Node instances.")
                if node.diagram is not self:
                    raise ConfigurationError("Grid layout node does not belong to this diagram.")
                if node in seen:
                    raise ConfigurationError("Grid layout nodes must be unique.")
                seen.add(node)
                normalized_row.append(node)
            normalized.append(normalized_row)
        self._manual_layout = ("grid", normalized)

    def _layout_grid(self, root: Node) -> None:
        levels: Dict[int, List[Node]] = defaultdict(list)
        queue: deque[Tuple[Node, int]] = deque([(root, 0)])
        all_nodes: List[Node] = []
        max_width = 0

        while queue:
            node, depth = queue.popleft()
            levels[depth].append(node)
            all_nodes.append(node)
            max_width = max(max_width, node.box_width)
            for child, _ in node.children:
                queue.append((child, depth + 1))

        if not all_nodes:
            return

        horizontal_gap = max(4, self.h_spacing * 2)
        cell_width = max_width + horizontal_gap
        level_heights: Dict[int, int] = {
            depth: max(child.height for child in nodes)
            for depth, nodes in levels.items()
        }

        current_y = 0
        min_x: Optional[int] = None

        for depth in sorted(levels.keys()):
            nodes_in_level = levels[depth]
            if not nodes_in_level:
                continue
            row_height = level_heights[depth]
            count = len(nodes_in_level)
            if count == 1:
                centers = [0.0]
            else:
                start_center = -((count - 1) * cell_width) / 2
                centers = [start_center + idx * cell_width for idx in range(count)]

            for center, node in zip(centers, nodes_in_level):
                x_pos = int(round(center - node.box_width / 2))
                y_pos = current_y + max((row_height - node.height) // 2, 0)
                node.x = x_pos
                node.y = y_pos
                node.branch_anchor_y = max(node.y - 1, 0)
                node.branch_from = None
                node.branch_row_index = 0
                if min_x is None or x_pos < min_x:
                    min_x = x_pos

            current_y += row_height + self.v_spacing

        if min_x is not None and min_x < 0:
            shift = -min_x
            for node in all_nodes:
                node.x += shift

    def _layout_node(self, node: Node):
        if not node.children:
            return

        bottom_children = [child for child, pos in node.children if pos == Position.BOTTOM]
        right_children = [child for child, pos in node.children if pos == Position.RIGHT]
        left_children = [child for child, pos in node.children if pos == Position.LEFT]
        top_children = [child for child, pos in node.children if pos == Position.TOP]

        if right_children:
            current_y = node.y
            for child in right_children:
                child.x = node.x + node.box_width + self.h_spacing - child.subtree_min_x
                child.y = current_y
                self._layout_node(child)
                current_y += child.subtree_height + self.v_spacing

        if left_children:
            current_y = node.y
            for child in left_children:
                child.x = node.x - self.h_spacing - child.subtree_max_x
                child.y = current_y
                self._layout_node(child)
                current_y += child.subtree_height + self.v_spacing

        if top_children:
            row_groups = self._group_bottom_children(top_children)

            row_layouts = []
            all_left_edges: List[int] = []
            all_right_edges: List[int] = []

            for row in row_groups:
                row_width = sum(child.subtree_width for child in row) + self.h_spacing * (len(row) - 1)
                start_x = node.x + (node.box_width // 2) - (row_width // 2)
                current_x = start_x
                entries = []
                for child in row:
                    child_x = current_x - child.subtree_min_x
                    left_edge = child_x + child.subtree_min_x
                    right_edge = child_x + child.subtree_max_x
                    entries.append((child, child_x, left_edge, right_edge))
                    all_left_edges.append(left_edge)
                    all_right_edges.append(right_edge)
                    current_x += child.subtree_width + self.h_spacing

                row_height = max(child.subtree_height for child in row)
                row_layouts.append((entries, row_height))

            branch_left = min(all_left_edges) if all_left_edges else node.x
            branch_right = max(all_right_edges) if all_right_edges else node.x + node.box_width

            base_y = node.y - self.v_spacing - 1
            overlapping_side_children = [
                child
                for child in right_children + left_children
                if child.x <= branch_right and (child.x + child.box_width - 1) >= branch_left
            ]
            if overlapping_side_children:
                side_min_top = min(child.y for child in overlapping_side_children)
                base_y = min(base_y, side_min_top - self.v_spacing)

            current_branch_y = min(base_y, node.y - 2)

            for row_index, (entries, row_height) in enumerate(row_layouts):
                branch_y = min(current_branch_y, node.y - 2)
                for child, child_x, _, _ in entries:
                    child.branch_row_index = row_index
                    child.branch_anchor_y = branch_y
                    child.branch_from = Position.TOP
                    child.x = child_x
                    child.y = branch_y - child.subtree_height
                    self._layout_node(child)

                min_child_top = min(child.y for child, _, _, _ in entries)
                current_branch_y = min_child_top - self.v_spacing - 1

        if bottom_children:
            row_groups = self._group_bottom_children(bottom_children)

            row_layouts = []
            all_left_edges: List[int] = []
            all_right_edges: List[int] = []

            for row in row_groups:
                row_width = sum(child.subtree_width for child in row) + self.h_spacing * (len(row) - 1)
                start_x = node.x + (node.box_width // 2) - (row_width // 2)
                current_x = start_x
                entries = []
                for child in row:
                    child_x = current_x - child.subtree_min_x
                    left_edge = child_x + child.subtree_min_x
                    right_edge = child_x + child.subtree_max_x
                    entries.append((child, child_x, left_edge, right_edge))
                    all_left_edges.append(left_edge)
                    all_right_edges.append(right_edge)
                    current_x += child.subtree_width + self.h_spacing

                row_height = max(child.subtree_height for child in row)
                row_layouts.append((entries, row_height))

            branch_left = min(all_left_edges)
            branch_right = max(all_right_edges)

            base_y = node.y + node.height + self.v_spacing
            overlapping_side_children = [
                child
                for child in right_children + left_children
                if child.x <= branch_right and (child.x + child.box_width - 1) >= branch_left
            ]
            if overlapping_side_children:
                side_max_bottom = max(child.y + child.subtree_height for child in overlapping_side_children)
                base_y = max(base_y, side_max_bottom + self.v_spacing)

            current_y = base_y
            for row_index, (entries, row_height) in enumerate(row_layouts):
                branch_y = current_y - 3
                min_branch = node.y + node.height
                if branch_y < min_branch:
                    branch_y = min_branch
                if branch_y > current_y - 2:
                    branch_y = current_y - 2
                for child, child_x, _, _ in entries:
                    child.branch_row_index = row_index
                    child.branch_anchor_y = branch_y
                    child.branch_from = Position.BOTTOM
                    child.x = child_x
                    child.y = current_y
                    self._layout_node(child)
                current_y += row_height + self.v_spacing

    def _shift_subtree(self, node: Node, dy: int):
        if dy == 0:
            return
        node.y += dy
        if node.branch_anchor_y is not None:
            node.branch_anchor_y += dy
        for child, _ in node.children:
            self._shift_subtree(child, dy)

    def _occupy_rect(self, occupied: Dict[int, List[Tuple[int, int]]], x0: int, x1: int, y0: int, y1: int):
        if x0 > x1 or y0 > y1:
            return
        for y in range(y0, y1 + 1):
            intervals = occupied.setdefault(y, [])
            intervals.append((x0, x1))
            intervals.sort()
            merged: List[Tuple[int, int]] = []
            for start, end in intervals:
                if not merged or start > merged[-1][1] + 1:
                    merged.append([start, end])
                else:
                    merged[-1][1] = max(merged[-1][1], end)
            occupied[y] = [(start, end) for start, end in merged]

    def _segment_blocked(self, occupied: Dict[int, List[Tuple[int, int]]], y: int, x0: int, x1: int) -> bool:
        if x0 > x1:
            x0, x1 = x1, x0
        for start, end in occupied.get(y, []):
            if start <= x1 and x0 <= end:
                return True
        return False

    def _ensure_branch_row_clear(
        self,
        node: Node,
        children: List[Node],
        branch_y: int,
        occupied: Dict[int, List[Tuple[int, int]]],
    ) -> int:
        parent_center = node.x + node.box_width // 2
        while True:
            collision = False
            for child in children:
                child_center = child.x + child.box_width // 2
                min_x, max_x = sorted((parent_center, child_center))
                if self._segment_blocked(occupied, branch_y, min_x, max_x):
                    collision = True
                    break
                for y in range(branch_y + 1, child.y):
                    if self._segment_blocked(occupied, y, child_center, child_center):
                        collision = True
                        break
                if collision:
                    break

            if not collision:
                return branch_y

            branch_y += 1
            min_child_top = min(child.y for child in children)
            max_allowed = min_child_top - 2
            if branch_y > max_allowed:
                delta = branch_y - max_allowed
                for child in children:
                    self._shift_subtree(child, delta)
                branch_y = max_allowed

    def _collect_rects(self, node: Node, rects: List[Tuple[int, int, int, int]]):
        rects.append((node.x, node.x + node.box_width - 1, node.y, node.y + node.height - 1))
        for child, _ in node.children:
            self._collect_rects(child, rects)

    def _subtree_overlap_delta(self, node: Node, occupied: Dict[int, List[Tuple[int, int]]]) -> int:
        rects: List[Tuple[int, int, int, int]] = []
        self._collect_rects(node, rects)
        delta = 0
        while True:
            collision = False
            for x0, x1, y0, y1 in rects:
                for y in range(y0 + delta, y1 + delta + 1):
                    if self._segment_blocked(occupied, y, x0, x1):
                        delta += 1
                        collision = True
                        break
                if collision:
                    break
            if not collision:
                return delta

    def _compute_row_overlap_delta(self, children: List[Node], occupied: Dict[int, List[Tuple[int, int]]]) -> int:
        max_delta = 0
        for child in children:
            max_delta = max(max_delta, self._subtree_overlap_delta(child, occupied))
        return max_delta

    def _auto_avoid_node(self, node: Node, occupied: Dict[int, List[Tuple[int, int]]]):
        self._occupy_rect(
            occupied,
            node.x,
            node.x + node.box_width - 1,
            node.y,
            node.y + node.height - 1,
        )

        top_children = [child for child, pos in node.children if pos == Position.TOP]
        if top_children:
            rows: Dict[int, List[Node]] = {}
            for child in top_children:
                rows.setdefault(child.branch_row_index, []).append(child)

            for row_index in sorted(rows.keys()):
                row_children = sorted(rows[row_index], key=lambda c: c.x)
                if not row_children:
                    continue
                branch_y = row_children[0].branch_anchor_y
                if branch_y is None:
                    continue
                parent_center = node.x + node.box_width // 2
                for child_node in row_children:
                    child_center = child_node.x + child_node.box_width // 2
                    min_x, max_x = sorted((parent_center, child_center))
                    self._occupy_rect(occupied, min_x, max_x, branch_y, branch_y)
                    child_bottom = child_node.y + child_node.height - 1
                    if child_bottom + 1 <= branch_y - 1:
                        self._occupy_rect(occupied, child_center, child_center, child_bottom + 1, branch_y - 1)

        bottom_children = [child for child, pos in node.children if pos == Position.BOTTOM]
        if bottom_children:
            rows: Dict[int, List[Node]] = {}
            for child in bottom_children:
                rows.setdefault(child.branch_row_index, []).append(child)

            for row_index in sorted(rows.keys()):
                row_children = sorted(rows[row_index], key=lambda c: c.x)
                if not row_children:
                    continue
                branch_y = row_children[0].branch_anchor_y
                if branch_y is None:
                    branch_y = node.y + node.height + 1
                while True:
                    branch_y = self._ensure_branch_row_clear(node, row_children, branch_y, occupied)
                    row_delta = self._compute_row_overlap_delta(row_children, occupied)
                    if row_delta:
                        for child in row_children:
                            self._shift_subtree(child, row_delta)
                        branch_y += row_delta
                        continue
                    break

                parent_center = node.x + node.box_width // 2
                for child in row_children:
                    child.branch_anchor_y = branch_y
                    child_center = child.x + child.box_width // 2
                    gap = child.y - branch_y
                    if gap < 2:
                        self._shift_subtree(child, 2 - gap)
                        child.branch_anchor_y = branch_y
                        child_center = child.x + child.box_width // 2
                    min_x, max_x = sorted((parent_center, child_center))
                    self._occupy_rect(occupied, min_x, max_x, branch_y, branch_y)
                    if child.y > branch_y + 1:
                        self._occupy_rect(occupied, child_center, child_center, branch_y + 1, child.y - 1)

        for child, pos in sorted(node.children, key=lambda item: item[0].x):
            if pos == Position.TOP:
                self._auto_avoid_node(child, occupied)
                continue
            delta = self._subtree_overlap_delta(child, occupied)
            if delta:
                self._shift_subtree(child, delta)
            self._auto_avoid_node(child, occupied)

    def _auto_avoid(self):
        occupied: Dict[int, List[Tuple[int, int]]] = {}
        self._auto_avoid_node(self.root, occupied)

    def _draw_box(self, canvas: Canvas, node: Node):
        x, y = node.x, node.y
        w = node.box_width
        inner_width = w - 2
        tokens_lines = getattr(node, "tokens_lines", None)
        if not tokens_lines:
            plain_line = node.text if node.text else ""
            tokens_lines = [[("text", char, max(wcwidth(char), 1)) for char in plain_line]]
        content_height = len(tokens_lines)
        bottom_y = y + content_height + 1

        canvas.set(x, y, self.chars.top_left)
        for i in range(1, w - 1):
            canvas.set(x + i, y, self.chars.horizontal)
        canvas.set(x + w - 1, y, self.chars.top_right)

        for idx, line_tokens in enumerate(tokens_lines):
            line_y = y + 1 + idx
            canvas.set(x, line_y, self.chars.vertical)
            canvas.set(x + w - 1, line_y, self.chars.vertical)

            for i in range(inner_width):
                canvas.set(x + 1 + i, line_y, " ")

            display_width = sum(token[2] for token in line_tokens if token[0] == "text")
            padding = 0
            if display_width < inner_width:
                padding = (inner_width - display_width) // 2
            cursor = x + 1 + padding
            pending_tags: List[str] = []
            for kind, value, width in line_tokens:
                if kind == "tag":
                    if value.startswith("[/"):
                        canvas.insert_markup(cursor, line_y, value)
                    else:
                        pending_tags.append(value)
                    continue
                glyph_width = max(width, 1)
                canvas.set(cursor, line_y, value, width=glyph_width)
                for tag in pending_tags:
                    canvas.insert_markup(cursor, line_y, tag)
                pending_tags.clear()
                cursor += glyph_width
            for tag in pending_tags:
                canvas.insert_markup(cursor, line_y, tag)

        canvas.set(x, bottom_y, self.chars.bottom_left)
        for i in range(1, w - 1):
            canvas.set(x + i, bottom_y, self.chars.horizontal)
        canvas.set(x + w - 1, bottom_y, self.chars.bottom_right)

    def _edge_anchor(self, node: Node, other: Node, outgoing: bool, prefer_horizontal: bool) -> Tuple[int, int, str]:
        center_x = node.x + node.box_width // 2
        center_y = node.y + node.height // 2
        other_center_x = other.x + other.box_width // 2
        other_center_y = other.y + other.height // 2
        dx = other_center_x - center_x
        dy = other_center_y - center_y

        if prefer_horizontal:
            if (dx >= 0 and outgoing) or (dx < 0 and not outgoing):
                x = node.x + node.box_width if outgoing else node.x - 1
                direction = "right" if outgoing else "left"
            else:
                x = node.x - 1 if outgoing else node.x + node.box_width
                direction = "left" if outgoing else "right"
            y = center_y
        else:
            if (dy >= 0 and outgoing) or (dy < 0 and not outgoing):
                y = node.y + node.height if outgoing else node.y - 1
                direction = "down" if outgoing else "up"
            else:
                y = node.y - 1 if outgoing else node.y + node.height
                direction = "up" if outgoing else "down"
            x = center_x
        return x, y, direction

    def _edge_path(self, start: Tuple[int, int], end: Tuple[int, int], prefer_horizontal: bool) -> List[Tuple[int, int]]:
        sx, sy = start
        ex, ey = end
        points: List[Tuple[int, int]] = [start]
        if prefer_horizontal:
            mid_x = (sx + ex) // 2
            points.append((mid_x, sy))
            points.append((mid_x, ey))
        else:
            mid_y = (sy + ey) // 2
            points.append((sx, mid_y))
            points.append((ex, mid_y))
        points.append(end)
        simplified: List[Tuple[int, int]] = [points[0]]
        for pt in points[1:]:
            if pt != simplified[-1]:
                simplified.append(pt)
        return simplified

    def _dirs_to_corner(self, prev: Tuple[int, int], cur: Tuple[int, int], nxt: Tuple[int, int]) -> Optional[str]:
        dx1 = cur[0] - prev[0]
        dy1 = cur[1] - prev[1]
        dx2 = nxt[0] - cur[0]
        dy2 = nxt[1] - cur[1]
        if dx1 == 0 and dy2 == 0:
            if dy1 > 0 and dx2 > 0:
                return self.chars.bottom_left
            if dy1 > 0 and dx2 < 0:
                return self.chars.bottom_right
            if dy1 < 0 and dx2 > 0:
                return self.chars.top_left
            if dy1 < 0 and dx2 < 0:
                return self.chars.top_right
        if dy1 == 0 and dx2 == 0:
            if dx1 > 0 and dy2 > 0:
                return self.chars.top_right
            if dx1 > 0 and dy2 < 0:
                return self.chars.bottom_right
            if dx1 < 0 and dy2 > 0:
                return self.chars.top_left
            if dx1 < 0 and dy2 < 0:
                return self.chars.bottom_left
        return None

    def _draw_corner_if_needed(
        self,
        canvas: Canvas,
        prev: Tuple[int, int],
        cur: Tuple[int, int],
        nxt: Tuple[int, int],
        problem_corners: Optional[Set[Tuple[int, int]]] = None,
        style: Optional[str] = None,
    ):
        dir_prev = self._direction_from_step(cur[0] - prev[0], cur[1] - prev[1])
        dir_next = self._direction_from_step(nxt[0] - cur[0], nxt[1] - cur[1])
        if not dir_prev or not dir_next or dir_prev == dir_next:
            return
        incoming = self._opposite_dir(dir_prev)
        outgoing = dir_next
        if incoming == outgoing:
            return
        x, y = cur
        existing = self._edge_state.get((x, y))
        if existing:
            existing["dirs"].update({incoming, outgoing})
            existing["is_corner"] = True
            if style and not existing.get("style"):
                existing["style"] = style
        else:
            data: Dict[str, object] = {"dirs": {incoming, outgoing}, "is_corner": True, "arrow": None}
            if style:
                data["style"] = style
            self._edge_state[(x, y)] = data
        state = self._edge_state[(x, y)]
        if problem_corners and (x, y) in problem_corners:
            state["corner_char"] = "•"
            return
        corner = self._dirs_to_corner(prev, cur, nxt)
        if corner:
            existing_corner = state.get("corner_char")
            if existing_corner and existing_corner != corner:
                state["corner_char"] = "•"
            else:
                state["corner_char"] = corner
        else:
            state["corner_char"] = "•"

    def _draw_segment(
        self,
        canvas: Canvas,
        start: Tuple[int, int],
        end: Tuple[int, int],
        style: Optional[str] = None,
    ):
        x0, y0 = start
        x1, y1 = end
        if x0 == x1 and y0 == y1:
            return
        if x0 == x1:
            step = 1 if y1 > y0 else -1
            y = y0
            while y != y1:
                key = (x0, y)
                state = self._edge_state.setdefault(key, {"dirs": set(), "is_corner": False, "arrow": None})
                if style and "style" not in state:
                    state["style"] = style
                state["dirs"].update({"up", "down"})
                y += step
        elif y0 == y1:
            step = 1 if x1 > x0 else -1
            x = x0
            while x != x1:
                key = (x, y0)
                state = self._edge_state.setdefault(key, {"dirs": set(), "is_corner": False, "arrow": None})
                if style and "style" not in state:
                    state["style"] = style
                state["dirs"].update({"left", "right"})
                x += step
        else:
            raise DiagramError("Edge segment harus ortogonal.")

    def _opposite_dir(self, direction: str) -> str:
        mapping = {"up": "down", "down": "up", "left": "right", "right": "left"}
        return mapping.get(direction, direction)

    def _draw_arrow(
        self,
        canvas: Canvas,
        pos: Tuple[int, int],
        direction: str,
        style: Optional[str] = None,
    ):
        arrow_map = {
            "up": self.chars.arrow_up,
            "down": self.chars.arrow_down,
            "left": self.chars.arrow_left,
            "right": self.chars.arrow_right,
        }
        if direction in arrow_map:
            x, y = pos
            self._set_connector_char(canvas, x, y, arrow_map[direction], style)

    def _build_edge_occupancy(self) -> Set[Tuple[int, int]]:
        rects: List[Tuple[int, int, int, int]] = []
        self._collect_rects(self.root, rects)
        blocked: Set[Tuple[int, int]] = set()
        for x0, x1, y0, y1 in rects:
            min_x = max(0, x0 - 1)
            max_x = min(self.canvas_width - 1, x1 + 1)
            min_y = max(0, y0 - 1)
            max_y = min(self.canvas_height - 1, y1 + 1)
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    blocked.add((x, y))
        return blocked

    def _simplify_path(self, path: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if len(path) <= 2:
            return path
        simplified: List[Tuple[int, int]] = [path[0]]
        prev = path[0]
        prev_dir: Optional[Tuple[int, int]] = None
        for idx in range(1, len(path)):
            cur = path[idx]
            dx = cur[0] - prev[0]
            dy = cur[1] - prev[1]
            if dx == 0 and dy == 0:
                continue
            direction = (0 if dx == 0 else dx // abs(dx), 0 if dy == 0 else dy // abs(dy))
            if prev_dir is not None and direction != prev_dir:
                simplified.append(prev)
            prev = cur
            prev_dir = direction
        simplified.append(path[-1])
        return simplified

    def _segment_clear_for_smoothing(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        blocked: Set[Tuple[int, int]],
    ) -> bool:
        x0, y0 = start
        x1, y1 = end
        if x0 == x1:
            step = 1 if y1 > y0 else -1
            y = y0 + step
            while y != y1:
                if (x0, y) in blocked:
                    return False
                y += step
            return True
        if y0 == y1:
            step = 1 if x1 > x0 else -1
            x = x0 + step
            while x != x1:
                if (x, y0) in blocked:
                    return False
                x += step
            return True
        return False

    def _smooth_path(self, path: List[Tuple[int, int]], blocked: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if len(path) <= 2:
            return path
        smoothed: List[Tuple[int, int]] = [path[0]]
        i = 1
        while i < len(path) - 1:
            prev_point = smoothed[-1]
            current_point = path[i]
            next_point = path[i + 1]
            if (
                (prev_point[0] == next_point[0] or prev_point[1] == next_point[1])
                and self._segment_clear_for_smoothing(prev_point, next_point, blocked)
            ):
                i += 1
                continue
            smoothed.append(current_point)
            i += 1
        smoothed.append(path[-1])
        return self._detour_zigzag(smoothed, blocked)

    def _direction_to_step(self, direction: str) -> Tuple[int, int]:
        mapping = {
            "right": (1, 0),
            "left": (-1, 0),
            "down": (0, 1),
            "up": (0, -1),
        }
        return mapping.get(direction, (0, 0))

    def _style_tokens(self, style: Optional[str]) -> Optional[Tuple[str, str]]:
        if not style:
            return None
        tag = style.strip()
        if not tag:
            return None
        open_tag = tag if tag.startswith("[") else f"[{tag}]"
        close_tag = "[/]"
        return open_tag, close_tag

    def _apply_style(self, canvas: Canvas, x: int, y: int, style: Optional[str]) -> None:
        tokens = self._style_tokens(style)
        if not tokens:
            return
        open_tag, close_tag = tokens
        canvas.insert_markup(x, y, open_tag, position="prefix")
        canvas.insert_markup(x, y, close_tag, position="suffix")

    def _set_connector_char(self, canvas: Canvas, x: int, y: int, char: str, style: Optional[str]) -> None:
        canvas.set(x, y, char)
        if style:
            self._apply_style(canvas, x, y, style)

    def _detour_zigzag(
        self,
        path: List[Tuple[int, int]],
        blocked: Set[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        if len(path) < 4:
            return path

        changed = True
        while changed:
            changed = False
            i = 1
            while i < len(path) - 2:
                prev_pt = path[i - 1]
                corner = path[i]
                next_corner = path[i + 1]
                after = path[i + 2]

                dir1 = self._direction_from_step(corner[0] - prev_pt[0], corner[1] - prev_pt[1])
                dir2 = self._direction_from_step(next_corner[0] - corner[0], next_corner[1] - corner[1])
                dir3 = self._direction_from_step(after[0] - next_corner[0], after[1] - next_corner[1])

                if not dir1 or not dir2 or not dir3:
                    i += 1
                    continue

                if dir1 == dir3 and dir1 != dir2:
                    step_dx, step_dy = self._direction_to_step(dir1)
                    candidate = (corner[0] + step_dx, corner[1] + step_dy)
                    if (
                        0 <= candidate[0] < self.canvas_width
                        and 0 <= candidate[1] < self.canvas_height
                        and candidate not in blocked
                        and candidate != next_corner
                        and candidate != after
                    ):
                        dx_after = after[0] - candidate[0]
                        dy_after = after[1] - candidate[1]
                        if ((dx_after == 0) ^ (dy_after == 0)) and (dx_after or dy_after):
                            if self._direction_from_step(dx_after, dy_after) == dir2:
                                new_path = path[: i + 1] + [candidate] + path[i + 2 :]
                                path = new_path
                                changed = True
                                i = max(i - 1, 1)
                                continue
                i += 1
        return path

    def _direction_from_step(self, dx: int, dy: int) -> Optional[str]:
        if dx > 0:
            return "right"
        if dx < 0:
            return "left"
        if dy > 0:
            return "down"
        if dy < 0:
            return "up"
        return None

    def _route_edge(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        hard_blocked: Set[Tuple[int, int]],
    ) -> Optional[List[Tuple[int, int]]]:
        if start == end:
            return [start]

        def nearest_free(point: Tuple[int, int]) -> Tuple[int, int]:
            x, y = point
            if (x, y) not in hard_blocked:
                return (x, y)
            queue = deque([point])
            seen = {point}
            moves = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            while queue:
                px, py = queue.popleft()
                for dx, dy in moves:
                    nx, ny = px + dx, py + dy
                    if not (0 <= nx < self.canvas_width and 0 <= ny < self.canvas_height):
                        continue
                    if (nx, ny) in seen:
                        continue
                    if (nx, ny) not in hard_blocked:
                        return (nx, ny)
                    seen.add((nx, ny))
                    queue.append((nx, ny))
            return point

        start = nearest_free(start)
        end = nearest_free(end)

        moves = [
            (1, 0, "right"),
            (-1, 0, "left"),
            (0, 1, "down"),
            (0, -1, "up"),
        ]

        blocked = set(hard_blocked)
        blocked.discard(start)
        blocked.discard(end)

        edge_state = self._edge_state

        turn_penalty = 3
        zigzag_penalty = 6
        proximity_penalty = 1
        shared_track_penalty = 4
        cross_penalty = 24
        corner_penalty = 12
        track_proximity_penalty = 2

        def heuristic(point: Tuple[int, int]) -> int:
            return abs(point[0] - end[0]) + abs(point[1] - end[1])

        def adjacent_penalty(point: Tuple[int, int]) -> int:
            x, y = point
            penalty = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < self.canvas_width and 0 <= ny < self.canvas_height):
                        continue
                    if (nx, ny) in blocked:
                        penalty += 1
            return penalty

        def edge_penalty(point: Tuple[int, int], direction: str) -> int:
            if point == end:
                return 0
            info = edge_state.get(point)
            penalty = 0
            if info:
                dirs = set(info.get("dirs", set()))
                arrow_dir = info.get("arrow")
                if arrow_dir:
                    dirs.add(arrow_dir)
                if info.get("is_corner") and info.get("corner_char"):
                    penalty += corner_penalty
                if dirs:
                    opp = self._opposite_dir(direction)
                    if direction in dirs or (opp and opp in dirs):
                        penalty += shared_track_penalty
                    else:
                        penalty += cross_penalty
            x, y = point
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.canvas_width and 0 <= ny < self.canvas_height):
                    continue
                if (nx, ny) == end:
                    continue
                neighbor = edge_state.get((nx, ny))
                if neighbor:
                    penalty += track_proximity_penalty
            return penalty

        start_state = (start, None, None)
        open_heap: List[Tuple[int, int, Tuple[int, int], Optional[str], Optional[str]]] = []
        start_priority = heuristic(start)
        heapq.heappush(open_heap, (start_priority, 0, start, None, None))

        came: Dict[Tuple[Tuple[int, int], Optional[str], Optional[str]], Tuple[Tuple[int, int], Optional[str], Optional[str]]] = {}
        best_cost: Dict[Tuple[Tuple[int, int], Optional[str], Optional[str]], int] = {start_state: 0}
        goal_state: Optional[Tuple[Tuple[int, int], Optional[str], Optional[str]]] = None

        while open_heap:
            f_cost, g_cost, (x, y), prev_dir, prev_prev_dir = heapq.heappop(open_heap)
            current_state = ((x, y), prev_dir, prev_prev_dir)
            recorded = best_cost.get(current_state)
            if recorded is not None and g_cost > recorded:
                continue
            if (x, y) == end:
                goal_state = current_state
                break

            for dx, dy, direction in moves:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.canvas_width and 0 <= ny < self.canvas_height):
                    continue
                if (nx, ny) in blocked:
                    continue

                step_cost = 1
                if prev_dir is not None and direction != prev_dir:
                    step_cost += turn_penalty
                    if (
                        prev_prev_dir is not None
                        and prev_dir != prev_prev_dir
                        and direction == prev_prev_dir
                    ):
                        step_cost += zigzag_penalty
                step_cost += proximity_penalty * adjacent_penalty((nx, ny))
                step_cost += edge_penalty((nx, ny), direction)

                next_cost = g_cost + step_cost
                next_state = ((nx, ny), direction, prev_dir)
                if next_cost >= best_cost.get(next_state, float("inf")):
                    continue

                best_cost[next_state] = next_cost
                came[next_state] = current_state
                priority = next_cost + heuristic((nx, ny))
                heapq.heappush(open_heap, (priority, next_cost, (nx, ny), direction, prev_dir))

        if goal_state is None:
            return None

        path: List[Tuple[int, int]] = []
        state: Optional[Tuple[Tuple[int, int], Optional[str], Optional[str]]] = goal_state
        while state is not None:
            point, _, _ = state
            path.append(point)
            state = came.get(state)
        path.reverse()

        path = self._smooth_path(path, blocked)
        return path

    def _reserve_edge_track(self, occupied: Set[Tuple[int, int]], point: Tuple[int, int]) -> None:
        x, y = point
        if not (0 <= x < self.canvas_width and 0 <= y < self.canvas_height):
            return
        occupied.add((x, y))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.canvas_width and 0 <= ny < self.canvas_height:
                occupied.add((nx, ny))

    def _draw_edge_label(
        self,
        canvas: Canvas,
        edge: Edge,
        path_points: List[Tuple[int, int]],
        occupied: Set[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        label = (edge.label or "").strip()
        if not label or len(path_points) < 2:
            return []

        label_text = f" {label} "
        best_segment = None
        best_score = (-1, -1)

        for idx in range(len(path_points) - 1):
            sx, sy = path_points[idx]
            ex, ey = path_points[idx + 1]
            if sx == ex and sy == ey:
                continue
            horizontal = sy == ey
            length = abs(ex - sx) if horizontal else abs(ey - sy)
            if length == 0:
                continue
            score = (1 if horizontal else 0, length)
            if score > best_score:
                best_score = score
                best_segment = (sx, sy, ex, ey, horizontal)

        if not best_segment:
            return []

        sx, sy, ex, ey, horizontal = best_segment
        occupied_cells: List[Tuple[int, int]] = []

        def can_place(start_x: int, y: int) -> bool:
            if not (0 <= y < self.canvas_height):
                return False
            for offset, _ in enumerate(label_text):
                x = start_x + offset
                if not (0 <= x < self.canvas_width):
                    return False
                if canvas.get(x, y) != " ":
                    return False
                if (x, y) in occupied:
                    return False
            return True

        def place(start_x: int, y: int) -> None:
            for offset, ch in enumerate(label_text):
                x = start_x + offset
                canvas.set(x, y, ch)
                occupied_cells.append((x, y))

        if horizontal:
            if ex < sx:
                sx, ex = ex, sx
            span = ex - sx
            mid = sx + span // 2
            start_x = mid - len(label_text) // 2
            start_x = max(0, min(self.canvas_width - len(label_text), start_x))
            for y_candidate in (sy - 1, sy + 1, sy - 2, sy + 2):
                if can_place(start_x, y_candidate):
                    place(start_x, y_candidate)
                    return occupied_cells
        else:
            if ey < sy:
                sy, ey = ey, sy
            span = ey - sy
            mid = sy + span // 2
            base_y = max(0, min(self.canvas_height - 1, mid))
            width = len(label_text)
            right_start = sx + 1
            left_start = sx - width
            candidates = [
                (right_start, base_y),
                (left_start, base_y),
                (right_start + 1, base_y),
                (left_start - 1, base_y),
            ]
            for start_x, y in candidates:
                if start_x < 0:
                    continue
                if start_x + len(label_text) > self.canvas_width:
                    continue
                if can_place(start_x, y):
                    place(start_x, y)
                    return occupied_cells

        return []

    def _draw_edge(
        self,
        canvas: Canvas,
        edge: Edge,
        hard_blocked: Set[Tuple[int, int]],
        label_occupied: Set[Tuple[int, int]],
    ):
        source = edge.source
        target = edge.target
        sx_center = source.x + source.box_width // 2
        sy_center = source.y + source.height // 2
        tx_center = target.x + target.box_width // 2
        ty_center = target.y + target.height // 2
        dx = tx_center - sx_center
        dy = ty_center - sy_center
        prefer_horizontal = abs(dx) >= abs(dy)

        start_x, start_y, start_dir = self._edge_anchor(source, target, True, prefer_horizontal)
        end_x, end_y, end_dir = self._edge_anchor(target, source, False, prefer_horizontal)

        edge_style = edge.style or self.connector_style

        path_points = self._route_edge((start_x, start_y), (end_x, end_y), hard_blocked)
        if not path_points:
            path_points = self._edge_path((start_x, start_y), (end_x, end_y), prefer_horizontal)
        path_points = self._simplify_path(path_points)

        directions: List[Optional[str]] = []
        for idx in range(len(path_points) - 1):
            step_dir = self._direction_from_step(
                path_points[idx + 1][0] - path_points[idx][0],
                path_points[idx + 1][1] - path_points[idx][1],
            )
            directions.append(step_dir)

        problem_corners: Set[Tuple[int, int]] = set()
        for i in range(1, len(directions) - 1):
            prev_dir = directions[i - 1]
            cur_dir = directions[i]
            next_dir = directions[i + 1]
            if not prev_dir or not cur_dir or not next_dir:
                continue
            if prev_dir != cur_dir and cur_dir != next_dir and prev_dir == next_dir:
                problem_corners.add(path_points[i])
                problem_corners.add(path_points[i + 1])

        for idx in range(len(path_points) - 1):
            seg_start = path_points[idx]
            seg_end = path_points[idx + 1]
            self._draw_segment(canvas, seg_start, seg_end, edge_style)
            if 0 < idx < len(path_points) - 1:
                self._draw_corner_if_needed(
                    canvas,
                    path_points[idx - 1],
                    path_points[idx],
                    path_points[idx + 1],
                    problem_corners,
                    edge_style,
                )

        label_cells = self._draw_edge_label(canvas, edge, path_points, label_occupied)

        for point in path_points[1:]:
            self._reserve_edge_track(label_occupied, point)
        for cell in label_cells:
            self._reserve_edge_track(label_occupied, cell)

        end_key = (end_x, end_y)
        entry = self._edge_state.setdefault(end_key, {"dirs": set(), "is_corner": False, "arrow": None})
        if edge_style and not entry.get("style"):
            entry["style"] = edge_style
        if entry.get("arrow") is None:
            entry["arrow"] = end_dir
        else:
            entry["dirs"].add(end_dir)
            entry["dirs"].add(self._opposite_dir(end_dir))
        if edge.bidirectional:
            start_key = (start_x, start_y)
            entry_start = self._edge_state.setdefault(start_key, {"dirs": set(), "is_corner": False, "arrow": None})
            if edge_style and not entry_start.get("style"):
                entry_start["style"] = edge_style
            entry_start["arrow"] = self._opposite_dir(start_dir)

    def _draw_edges(self, canvas: Canvas):
        if not self._edges:
            return
        hard_blocked = self._build_edge_occupancy()
        label_occupied = set(hard_blocked)
        self._edge_state = {}
        for edge in self._edges:
            self._draw_edge(canvas, edge, hard_blocked, label_occupied)
        for (x, y), info in self._edge_state.items():
            dirs = info.get("dirs", set())
            style = info.get("style") or self.connector_style
            if info.get("is_corner") and info.get("corner_char"):
                self._set_connector_char(canvas, x, y, info["corner_char"], style)
                continue
            arrow_dir = info.get("arrow")
            if arrow_dir:
                self._draw_arrow(canvas, (x, y), arrow_dir, style)
            elif dirs:
                self._set_connector_char(canvas, x, y, self._dirs_to_char(dirs), style)

    def _draw_connector(self, canvas: Canvas, parent: Node, child: Node, position: Position):
        style = self.connector_style
        if position == Position.BOTTOM:
            p_x = parent.x + parent.box_width // 2
            p_y = parent.y + parent.height

            c_x = child.x + child.box_width // 2
            c_y = child.y

            siblings = [c for c, pos in parent.children if pos == Position.BOTTOM]

            if len(siblings) == 1:
                for y in range(p_y, c_y - 1):
                    self._write_dirs(canvas, p_x, y, {"up", "down"})
                self._set_connector_char(canvas, c_x, c_y - 1, self.chars.arrow_down, style)
            else:
                branch_groups = {}
                for s in siblings:
                    branch_y = getattr(s, "branch_anchor_y", s.y - 1)
                    branch_groups.setdefault(branch_y, []).append(s)

                max_branch = max(branch_groups.keys())
                for y in range(p_y, max_branch + 1):
                    self._write_dirs(canvas, p_x, y, {"up", "down"})

                for branch_y in sorted(branch_groups.keys()):
                    row_children = sorted(branch_groups[branch_y], key=lambda n: n.x + n.box_width // 2)
                    for child_node in row_children:
                        center = child_node.x + child_node.box_width // 2
                        if center > p_x:
                            for x_pos in range(p_x + 1, center):
                                self._write_dirs(canvas, x_pos, branch_y, {"left", "right"})
                            self._write_dirs(canvas, p_x, branch_y, {"right"})
                            self._write_dirs(canvas, center, branch_y, {"down", "left"})
                        elif center < p_x:
                            for x_pos in range(center + 1, p_x):
                                self._write_dirs(canvas, x_pos, branch_y, {"left", "right"})
                            self._write_dirs(canvas, p_x, branch_y, {"left"})
                            self._write_dirs(canvas, center, branch_y, {"down", "right"})
                        else:
                            self._write_dirs(canvas, p_x, branch_y, {"down"})

                        s_y = child_node.y
                        for y_pos in range(branch_y + 1, s_y - 1):
                            self._write_dirs(canvas, center, y_pos, {"up", "down"})
                        self._set_connector_char(canvas, center, s_y - 1, self.chars.arrow_down, style)

        elif position == Position.RIGHT:
            p_x = parent.x + parent.box_width
            p_y = parent.y + parent.height // 2

            c_x = child.x
            c_y = child.y + child.height // 2

            if p_y == c_y:
                for x in range(p_x, c_x - 1):
                    self._set_connector_char(canvas, x, p_y, self.chars.horizontal, style)
                self._set_connector_char(canvas, c_x - 1, c_y, self.chars.arrow_right, style)
            else:
                corner_x = p_x + self.h_spacing // 2

                for x in range(p_x, corner_x):
                    self._set_connector_char(canvas, x, p_y, self.chars.horizontal, style)

                if c_y > p_y:
                    self._write_dirs(canvas, corner_x, p_y, {"left", "down"}, style)
                    for y in range(p_y + 1, c_y):
                        self._set_connector_char(canvas, corner_x, y, self.chars.vertical, style)
                    self._write_dirs(canvas, corner_x, c_y, {"up", "right"}, style)
                else:
                    self._write_dirs(canvas, corner_x, p_y, {"left", "up"}, style)
                    for y in range(c_y + 1, p_y):
                        self._set_connector_char(canvas, corner_x, y, self.chars.vertical, style)
                    self._write_dirs(canvas, corner_x, c_y, {"down", "right"}, style)

                for x in range(corner_x + 1, c_x - 1):
                    self._set_connector_char(canvas, x, c_y, self.chars.horizontal, style)
                self._set_connector_char(canvas, c_x - 1, c_y, self.chars.arrow_right, style)

        elif position == Position.LEFT:
            p_x = parent.x
            p_y = parent.y + parent.height // 2

            c_x = child.x + child.box_width
            c_y = child.y + child.height // 2

            if p_y == c_y:
                for x in range(c_x + 1, p_x):
                    self._set_connector_char(canvas, x, p_y, self.chars.horizontal, style)
                self._set_connector_char(canvas, c_x + 1, c_y, self.chars.arrow_left, style)
            else:
                corner_x = p_x - self.h_spacing // 2

                for x in range(corner_x + 1, p_x):
                    self._set_connector_char(canvas, x, p_y, self.chars.horizontal, style)

                if c_y > p_y:
                    self._write_dirs(canvas, corner_x, p_y, {"right", "down"}, style)
                    for y in range(p_y + 1, c_y):
                        self._set_connector_char(canvas, corner_x, y, self.chars.vertical, style)
                    self._write_dirs(canvas, corner_x, c_y, {"up", "left"}, style)
                else:
                    self._write_dirs(canvas, corner_x, p_y, {"right", "up"}, style)
                    for y in range(c_y + 1, p_y):
                        self._set_connector_char(canvas, corner_x, y, self.chars.vertical, style)
                    self._write_dirs(canvas, corner_x, c_y, {"down", "left"}, style)

                for x in range(c_x + 1, corner_x):
                    self._set_connector_char(canvas, x, c_y, self.chars.horizontal, style)
                self._set_connector_char(canvas, c_x + 1, c_y, self.chars.arrow_left, style)

        elif position == Position.TOP:
            p_x = parent.x + parent.box_width // 2
            p_y = parent.y

            siblings = [c for c, pos in parent.children if pos == Position.TOP]
            branch_groups = {}
            for s in siblings:
                branch_y = getattr(s, "branch_anchor_y", s.y + s.height)
                branch_groups.setdefault(branch_y, []).append(s)

            if not branch_groups:
                return

            min_branch = min(branch_groups.keys())
            for y in range(p_y - 1, min_branch - 1, -1):
                self._write_dirs(canvas, p_x, y, {"up", "down"})

            for branch_y in sorted(branch_groups.keys(), reverse=True):
                row_children = sorted(branch_groups[branch_y], key=lambda n: n.x + n.box_width // 2)
                for child_node in row_children:
                    center = child_node.x + child_node.box_width // 2
                    if center > p_x:
                        for x_pos in range(p_x + 1, center):
                            self._write_dirs(canvas, x_pos, branch_y, {"left", "right"})
                        self._write_dirs(canvas, p_x, branch_y, {"right"})
                        self._write_dirs(canvas, center, branch_y, {"up", "left"})
                    elif center < p_x:
                        for x_pos in range(center + 1, p_x):
                            self._write_dirs(canvas, x_pos, branch_y, {"left", "right"})
                        self._write_dirs(canvas, p_x, branch_y, {"left"})
                        self._write_dirs(canvas, center, branch_y, {"up", "right"})
                    else:
                        self._write_dirs(canvas, p_x, branch_y, {"up"})

                    c_bottom_local = child_node.y + child_node.height - 1
                    for y_pos in range(branch_y - 1, c_bottom_local, -1):
                        self._write_dirs(canvas, center, y_pos, {"up", "down"})
                    self._set_connector_char(canvas, center, c_bottom_local + 1, self.chars.arrow_up, style)

    def _draw_all_nodes(self, canvas: Canvas, node: Node):
        self._draw_box(canvas, node)

        for child, position in node.children:
            self._draw_connector(canvas, node, child, position)
            self._draw_all_nodes(canvas, child)

    def _normalize_positions(self, node: Node, offset_x: int = 0, offset_y: int = 0):
        min_x = min_y = float("inf")

        def find_min(n: Node):
            nonlocal min_x, min_y
            min_x = min(min_x, n.x)
            min_y = min(min_y, n.y)
            for child, _ in n.children:
                find_min(child)

        find_min(node)

        def shift(n: Node, dx: int, dy: int):
            n.x += dx
            n.y += dy
            if n.branch_anchor_y is not None:
                n.branch_anchor_y += dy
            for child, _ in n.children:
                shift(child, dx, dy)

        if min_x < 0 or min_y < 0:
            shift(node, abs(min_x) if min_x < 0 else 0, abs(min_y) if min_y < 0 else 0)

    def _compute_bounds(self, node: Node) -> Tuple[int, int, int, int]:
        min_x = node.x
        max_x = node.x + node.box_width - 1
        min_y = node.y
        max_y = node.y + node.height - 1

        for child, _ in node.children:
            c_min_x, c_max_x, c_min_y, c_max_y = self._compute_bounds(child)
            min_x = min(min_x, c_min_x)
            max_x = max(max_x, c_max_x)
            min_y = min(min_y, c_min_y)
            max_y = max(max_y, c_max_y)

        return min_x, max_x, min_y, max_y

    def _validate_bounds(self, required_width: int, required_height: int):
        if (
            self._canvas_width_config is not None
            and required_width > self._canvas_width_config
        ):
            raise LayoutOverflowError(
                "Diagram width exceeds configured canvas_width. Increase canvas_width "
                "or allow auto-sizing by leaving it unset."
            )
        if (
            self._canvas_height_config is not None
            and required_height > self._canvas_height_config
        ):
            raise LayoutOverflowError(
                "Diagram height exceeds configured canvas_height. Increase canvas_height "
                "or allow auto-sizing by leaving it unset."
            )

    def render(self, include_markup: bool = False, fit_to_terminal: bool = True) -> str:
        original_layout_width = self._current_layout_width
        effective_layout_width = self.max_layout_width
        if fit_to_terminal:
            columns = shutil.get_terminal_size(fallback=(80, 24)).columns
            adjusted = columns - 6
            if adjusted >= 24:
                effective_layout_width = min(effective_layout_width, adjusted) if effective_layout_width else adjusted
        self._current_layout_width = effective_layout_width

        original_canvas_width = self.canvas_width
        original_canvas_height = self.canvas_height

        try:
            self._calculate_layout()
            self._normalize_positions(self.root)
            min_x, max_x, min_y, max_y = self._compute_bounds(self.root)
            content_width = max_x - min_x + 1
            content_height = max_y - min_y + 1

            auto_padding = 8
            width = (
                self._canvas_width_config
                if self._canvas_width_config is not None
                else max(32, content_width + auto_padding)
            )
            height = (
                self._canvas_height_config
                if self._canvas_height_config is not None
                else max(32, content_height + auto_padding)
            )

            self._validate_bounds(content_width, content_height)

            original_canvas_width = self.canvas_width
            original_canvas_height = self.canvas_height
            self.canvas_width = width
            self.canvas_height = height

            canvas = Canvas(width=width, height=height)
            self._draw_all_nodes(canvas, self.root)
            self._draw_edges(canvas)
            return canvas.render(crop=True, include_markup=include_markup)
        finally:
            self._current_layout_width = original_layout_width
            self.canvas_width = original_canvas_width
            self.canvas_height = original_canvas_height

    def render_paginated(
        self,
        *,
        include_markup: bool = False,
        fit_to_terminal: bool = True,
        page_height: Optional[int] = None,
        page_width: Optional[int] = None,
        overlap: int = 0,
    ) -> List[str]:
        text = self.render(include_markup=include_markup, fit_to_terminal=fit_to_terminal)
        if not text:
            return [""]

        lines = text.split("\n")

        if page_width is not None and page_width > 0:
            wrapped: List[str] = []
            for line in lines:
                if len(line) <= page_width:
                    wrapped.append(line)
                    continue
                start = 0
                while start < len(line):
                    wrapped.append(line[start : start + page_width])
                    start += page_width
            lines = wrapped

        if not lines:
            lines = [""]

        if page_height is None or page_height <= 0:
            terminal_lines = shutil.get_terminal_size(fallback=(80, 24)).lines
            if terminal_lines <= 0:
                terminal_lines = 24
            page_height = max(1, terminal_lines - 2)

        if overlap < 0:
            overlap = 0
        if overlap >= page_height:
            overlap = page_height - 1

        step = max(1, page_height - overlap)

        pages: List[str] = []
        index = 0
        total_lines = len(lines)
        while index < total_lines:
            end = min(total_lines, index + page_height)
            pages.append("\n".join(lines[index:end]))
            if end == total_lines:
                break
            index += step

        return pages

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return self.render()

    def render_markup(self) -> str:
        return self.render(include_markup=True)
