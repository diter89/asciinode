from asciinode.ascii_diagram import Diagram, Shape
from rich import print


def main() -> None:
    diagram = Diagram("Shape Demonstration")

    print("[bold cyan]Testing Different Node Shapes:[/bold cyan]\n")

    # Rectangle (default)
    rect = diagram.add_bottom("Rectangle", shape=Shape.RECTANGLE)

    # Diamond for decisions
    decision = rect.add_bottom("Decision Point", shape=Shape.DIAMOND)

    # Double box for critical components
    critical =decision.add_bottom("Critical System", shape=Shape.DOUBLE_BOX)

    # Add some connections

    print(diagram.render(include_markup=True))

if __name__ == "__main__":
    main()
