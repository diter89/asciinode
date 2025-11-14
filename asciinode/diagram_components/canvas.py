from typing import Dict, List, Tuple

from ..errors import LayoutOverflowError


class Canvas:

    def __init__(self, width: int = 200, height: int = 100):
        self.width = width
        self.height = height
        self.grid = [[" " for _ in range(width)] for _ in range(height)]
        self.cell_widths = [[1 for _ in range(width)] for _ in range(height)]
        self.min_x = width
        self.max_x = 0
        self.min_y = height
        self.max_y = 0
        self.markup: Dict[Tuple[int, int], Dict[str, List[str]]] = {}

    def _clear_markup(self, x: int, y: int) -> None:
        self.markup.pop((x, y), None)

    def _clear_glyph_at(self, x: int, y: int) -> None:
        width = self.cell_widths[y][x]
        base_x = x
        if width == 0:
            base_x = x - 1
            while base_x >= 0 and self.cell_widths[y][base_x] == 0:
                base_x -= 1
            if base_x < 0:
                return
            width = self.cell_widths[y][base_x]
            x = base_x
        if width <= 1:
            if 0 <= x < self.width:
                self._clear_markup(x, y)
            return
        for i in range(width):
            xi = x + i
            if 0 <= xi < self.width:
                self.grid[y][xi] = " "
                self.cell_widths[y][xi] = 1
                self._clear_markup(xi, y)

    def set(self, x: int, y: int, char: str, width: int = 1) -> None:
        if not (0 <= y < self.height and 0 <= x < self.width):
            raise LayoutOverflowError(
                "Diagram content exceeds canvas bounds at "
                f"({x}, {y}). Increase canvas size via Diagram(..., "
                "canvas_width=..., canvas_height=...)."
            )
        if width < 1:
            width = 1

        self._clear_glyph_at(x, y)
        self._clear_markup(x, y)

        self.grid[y][x] = char
        self.cell_widths[y][x] = width
        for i in range(1, width):
            xi = x + i
            if not (0 <= xi < self.width):
                raise LayoutOverflowError(
                    "Diagram content exceeds canvas bounds at "
                    f"({xi}, {y}). Increase canvas size via Diagram(..., "
                    "canvas_width=..., canvas_height=...)."
                )
            self.grid[y][xi] = " "
            self.cell_widths[y][xi] = 0
            self._clear_markup(xi, y)

        for i in range(width):
            xi = x + i
            self.min_x = min(self.min_x, xi)
            self.max_x = max(self.max_x, xi)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)

    def get(self, x: int, y: int) -> str:
        if 0 <= y < self.height and 0 <= x < self.width:
            if self.cell_widths[y][x] == 0:
                return " "
            return self.grid[y][x]
        return " "

    def insert_markup(self, x: int, y: int, markup: str, *, position: str = "prefix") -> None:
        if not markup:
            return
        if position not in {"prefix", "suffix"}:
            position = "prefix"
        cell = self.markup.setdefault((x, y), {"prefix": [], "suffix": []})
        cell[position].append(markup)

    def render(self, crop: bool = True, include_markup: bool = False) -> str:
        if crop and self.max_x > 0:
            lines: List[str] = []
            for y in range(self.min_y, self.max_y + 1):
                parts: List[str] = []
                for x in range(self.min_x, self.max_x + 1):
                    if self.cell_widths[y][x] == 0:
                        continue
                    markup_cell = self.markup.get((x, y)) if include_markup else None
                    if markup_cell:
                        parts.extend(markup_cell.get("prefix", []))
                    parts.append(self.grid[y][x])
                    if markup_cell:
                        parts.extend(markup_cell.get("suffix", []))
                line = "".join(parts).rstrip()
                lines.append(line)
            return "\n".join(lines)

        lines: List[str] = []
        for y in range(self.height):
            parts: List[str] = []
            for x in range(self.width):
                if self.cell_widths[y][x] == 0:
                    continue
                markup_cell = self.markup.get((x, y)) if include_markup else None
                if markup_cell:
                    parts.extend(markup_cell.get("prefix", []))
                parts.append(self.grid[y][x])
                if markup_cell:
                    parts.extend(markup_cell.get("suffix", []))
            lines.append("".join(parts))
        return "\n".join(lines)
