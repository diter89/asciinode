from asciinode.ascii_diagram import Diagram
from rich import print


def build_simple_tree() -> Diagram:
    diagram = Diagram("Company")

    engineering = diagram.add_bottom("Engineering")
    frontend = engineering.add_bottom("Frontend")
    backend = engineering.add_bottom("Backend")

    react_dev = frontend.add_bottom("React Dev")
    ui_designer = frontend.add_bottom("UI Designer")

    api_dev = backend.add_bottom("API Dev")
    db_admin = backend.add_bottom("DB Admin")

    return diagram


def main() -> None:
    diagram = build_simple_tree()

    print("[bold cyan]Full Company Structure:[/bold cyan]\n")
    print(diagram.render(include_markup=True))

    print("\n" + "=" * 40 + "\n")

    engineering_node = diagram.root.children[0][0]
    print("[bold green]Engineering Only:[/bold green]\n")
    print(diagram.render_subtree(engineering_node, include_markup=True))

    print("\n" + "=" * 40 + "\n")

    frontend_node = engineering_node.children[0][0]
    print("[bold yellow]Frontend Team:[/bold yellow]\n")
    print(diagram.render_subtree(frontend_node, include_markup=True))

    print("\n" + "=" * 40 + "\n")

    print("[bold magenta]Engineering (depth=1):[/bold magenta]\n")
    print(diagram.render_subtree(engineering_node, depth=1, include_markup=True))


if __name__ == "__main__":
    main()
