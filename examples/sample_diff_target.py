from asciinode.ascii_diagram import Diagram
from asciinode.diagram_components.diff import diff
from rich import print
from rich.console import Console

console = Console()


def _fake_llm(messages, **kwargs):
    query = messages[-1]["content"]
    return {"choices": [{"message": {"content": f"AI Response: {query.upper()}"}}]}


class CustomDiagram(Diagram):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("connector_style", "[#888888]")
        kwargs.setdefault("llm_client", _fake_llm)
        super().__init__(*args, **kwargs)


def create_original_diagram() -> Diagram:
    """Create the original diagram structure."""
    diagram = CustomDiagram("System Architecture")

    # Add basic structure
    api_layer = diagram.add_right("API Layer")
    database = diagram.add_bottom("Database")
    cache = diagram.add_left("Cache System")

    # Add some LLM nodes
    api_layer.add_bottom("What is REST API?", llm_answer=True)
    database.add_right("Explain database indexing", llm_answer=True)

    return diagram


def create_modified_diagram() -> Diagram:
    """Create a modified version of the diagram."""
    diagram = CustomDiagram("Cloud Architecture")  # Changed title

    # Similar structure but with changes
    api_layer = diagram.add_right("API Gateway")  # Changed name
    database = diagram.add_bottom("Database")
    cache = diagram.add_left("Redis Cache")  # Changed name

    # Add new node
    monitoring = diagram.add_top("Monitoring System")  # New node

    # Modify existing LLM nodes
    api_layer.add_bottom("What is GraphQL?", llm_answer=True)  # Changed query
    database.add_right("Explain database indexing", llm_answer=True)  # Same

    # Add new LLM node
    monitoring.add_right("How to monitor microservices?", llm_answer=True)  # New

    return diagram


def demonstrate_diff():
    """Demonstrate the diff functionality between two diagrams."""
    print("[bold cyan]Creating original diagram...[/bold cyan]\n")

    original = create_original_diagram()
    print("[bold green]Original Diagram:[/bold green]")
    print(original.render(include_markup=True))

    console.rule("")

    print("[bold cyan]Creating modified diagram...[/bold cyan]\n")

    modified = create_modified_diagram()
    print("[bold green]Modified Diagram:[/bold green]")
    print(modified.render(include_markup=True))

    console.rule("")

    # Perform diff
    print("[bold yellow]Performing diff analysis...[/bold yellow]\n")

    result = diff(original, modified)

    # Display diff results
    print("[bold red]▣ Diff Analysis Results:[/bold red]")

    if not result.has_changes():
        print("✓ [green]No differences found between diagrams.[/green]")
        return

    # Summary statistics
    total_changes = (
        len(result.added_nodes)
        + len(result.removed_nodes)
        + len(result.changed_nodes)
        + len(result.added_edges)
        + len(result.removed_edges)
    )

    print(f"▲ [yellow]Total changes detected: {total_changes}[/yellow]\n")

    if result.added_nodes:
        print(f"◯ [green]Added nodes ({len(result.added_nodes)}):[/green]")
        for node in result.added_nodes:
            print(f"  + [green]{node}[/green]")
        print()

    if result.removed_nodes:
        print(f"● [red]Removed nodes ({len(result.removed_nodes)}):[/red]")
        for node in result.removed_nodes:
            print(f"  - [red]{node}[/red]")
        print()

    if result.changed_nodes:
        print(f"◐ [yellow]Modified nodes ({len(result.changed_nodes)}):[/yellow]")
        for identifier, old_text, new_text in result.changed_nodes:
            print(
                f"  ∼ [yellow]{identifier}:[/yellow] [dim]'{old_text}'[/dim] → [bold]'{new_text}'[/bold]"
            )
        print()

    if result.added_edges:
        print(f"◯ [green]Added connections ({len(result.added_edges)}):[/green]")
        for source, target in result.added_edges:
            print(f"  + [green]{source} → {target}[/green]")
        print()

    if result.removed_edges:
        print(f"● [red]Removed connections ({len(result.removed_edges)}):[/red]")
        for source, target in result.removed_edges:
            print(f"  - [red]{source} → {target}[/red]")
        print()

    print(
        f"★ [bold cyan]Analysis complete! Found {total_changes} total changes.[/bold cyan]"
    )


if __name__ == "__main__":
    demonstrate_diff()
