from typing_extensions import Dict
from asciinode.ascii_diagram import Diagram  # as baseDiagram
from rich import print


def main():
    diagram = Diagram("workflow", box_style="rounded")
    root = diagram.root

    child = diagram.add(
        "siapa pendiri sentient-agi",
        llm_answer=True,
        title="[green bold] pendiri sentient-agi [/green bold]",
    )
    child1 = diagram.add_bottom("whait is nillion ?", llm_answer=True)
    child1.add_bottom("what is calendar ?", llm_answer=True)

    untukrot = root.add_left(
        "hello", llm_answer=True, llm_system_prompt="you are help assistent"
    )
    untukrot1 = root.add_right("apa kabar", llm_answer=True)
    print(diagram.render(include_markup=True))


main()
