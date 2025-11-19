from asciinode.ascii_diagram import Diagram as BaseDiagram, Position
from rich import print


def _fake_llm(messages, **kwargs):
    query = messages[-1]["content"]
    return {"choices": [{"message": {"content": f"AI Response: {query.upper()}"}}]}


class Diagram(BaseDiagram):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("connector_style", "[#0a7e89]")
        kwargs.setdefault("llm_client", _fake_llm)
        super().__init__(*args, **kwargs)


def main() -> None:
    diagram = Diagram("System Architecture")

    database = diagram.add_right("Database Layer")
    database.add_bottom("Manual Configuration")

    api_analysis = database.add_llm_answer(
        "analyze database performance bottlenecks", position=Position.LEFT
    )

    optimization = api_analysis.add_llm_answer(
        "recommend scaling strategies for high-traffic applications",
        position=Position.BOTTOM,
    )

    monitoring = optimization.add_right("Monitoring Dashboard")

    print(diagram.render(include_markup=True))


if __name__ == "__main__":
    main()
