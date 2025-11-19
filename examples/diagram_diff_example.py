"""Example demonstrating diff between two diagrams."""

from asciinode.ascii_diagram import Diagram
from asciinode.diagram_components.diff import diff


def build_base_diagram() -> Diagram:
    diagram = Diagram("Root")
    api = diagram.add_right("API Gateway")
    worker = api.add_bottom("Worker Pool")
    worker.add_bottom("Data Store")
    return diagram


def build_modified_diagram() -> Diagram:
    diagram = build_base_diagram()
    diagram.root.children[0][0].text = "API Layer"
    diagram.root.add_left("Cache")
    return diagram


def main() -> None:
    original = build_base_diagram()
    modified = build_modified_diagram()

    result = diff(original, modified)
    print("Added nodes:", result.added_nodes)
    print("Removed nodes:", result.removed_nodes)
    print("Changed nodes:", result.changed_nodes)
    print("Added edges:", result.added_edges)
    print("Removed edges:", result.removed_edges)


if __name__ == "__main__":
    main()
