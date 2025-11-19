from asciinode.ascii_diagram import Diagram
from rich import print


def main() -> None:
    diagram = Diagram("Main System")

    api = diagram.add_bottom("API Service", title="Layer 1")
    database = api.add_bottom("Database", title="Storage")
    cache = database.add_bottom("Redis Cache", title="Memory")

    print("[bold cyan]Simple Title Example:[/bold cyan]\n")
    print(diagram.render(include_markup=True))


if __name__ == "__main__":
    main()
