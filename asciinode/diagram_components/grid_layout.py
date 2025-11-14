from typing import List, Sequence

from .node import Node


class GridLayout:

    def __init__(
        self,
        diagram: "Diagram",
        rows: Sequence[Sequence[Node]],
        *,
        horizontal_spacing: int,
        vertical_spacing: int,
    ) -> None:
        from .diagram import Diagram

        if not isinstance(diagram, Diagram):
            raise TypeError("diagram must be a Diagram instance")

        if not rows:
            raise ValueError("Grid layout requires at least one row.")

        row_lengths = {len(row) for row in rows}
        if not row_lengths or 0 in row_lengths:
            raise ValueError("Grid layout rows must be non-empty.")
        if len(row_lengths) != 1:
            raise ValueError("All grid rows must have the same number of nodes.")

        self._diagram = diagram
        self._rows: List[List[Node]] = [list(row) for row in rows]
        self._horizontal_spacing = max(1, horizontal_spacing)
        self._vertical_spacing = max(1, vertical_spacing)

    def apply(self) -> None:
        rows = self._rows
        column_count = len(rows[0])

        column_widths = [0] * column_count
        row_heights = []

        for row in rows:
            row_height = 0
            for idx, node in enumerate(row):
                column_widths[idx] = max(column_widths[idx], node.box_width)
                row_height = max(row_height, node.height)
            row_heights.append(row_height)

        x_positions = []
        current_x = 0
        for width in column_widths:
            x_positions.append(current_x)
            current_x += width + self._horizontal_spacing

        current_y = 0
        for row_index, row in enumerate(rows):
            for col_index, node in enumerate(row):
                col_width = column_widths[col_index]
                offset_x = x_positions[col_index] + max((col_width - node.box_width) // 2, 0)
                node.x = offset_x
                node.y = current_y
                node.branch_anchor_y = None
                node.branch_from = None
                node.branch_row_index = 0
            current_y += row_heights[row_index] + self._vertical_spacing

        self._diagram._normalize_positions(self._diagram.root)
