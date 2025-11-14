from asciinode.ascii_diagram import Diagram as BaseDiagram
from rich import print


class Diagram(BaseDiagram):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("connector_style", "[#0a7e89]")
        super().__init__(*args, **kwargs)


def main() -> None:
    diagram = Diagram("test")
    diagram.add("hello word").add_bottom("hello 1")
    diagram.add_left("test")
    print(diagram.render(include_markup=True))


if __name__ == "__main__":
    main()

