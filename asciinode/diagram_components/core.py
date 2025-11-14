from dataclasses import dataclass
from enum import Enum


class Position(Enum):

    BOTTOM = "bottom"
    RIGHT = "right"
    LEFT = "left"
    TOP = "top"


@dataclass
class BoxChars:

    top_left: str = "╭"
    top_right: str = "╮"
    bottom_left: str = "╰"
    bottom_right: str = "╯"

    horizontal: str = "─"
    vertical: str = "│"

    tee_down: str = "┬"
    tee_up: str = "┴"
    tee_right: str = "├"
    tee_left: str = "┤"
    cross: str = "┼"

    arrow_down: str = "▼"
    arrow_right: str = "►"
    arrow_left: str = "◄"
    arrow_up: str = "▲"

    @classmethod
    def for_style(cls, style: str) -> "BoxChars":
        key = style.lower().strip()
        if key in {"rounded", "round", "modern"}:
            return cls()
        if key in {"square", "line", "box"}:
            return cls(
                top_left="┌",
                top_right="┐",
                bottom_left="└",
                bottom_right="┘",
                horizontal="─",
                vertical="│",
                tee_down="┬",
                tee_up="┴",
                tee_right="├",
                tee_left="┤",
                cross="┼",
            )
        if key in {"ascii", "plain"}:
            return cls(
                top_left="+",
                top_right="+",
                bottom_left="+",
                bottom_right="+",
                horizontal="-",
                vertical="|",
                tee_down="+",
                tee_up="+",
                tee_right="+",
                tee_left="+",
                cross="+",
                arrow_down="v",
                arrow_right=">",
                arrow_left="<",
                arrow_up="^",
            )
        raise ValueError(f"Unknown box style: {style}")
