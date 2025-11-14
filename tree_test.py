from asciinode.ascii_diagram import Diagram
from rich.console import Console

diagram = Diagram(
    "Tree Test",
    vertical_spacing=2,
    horizontal_spacing=3,
    canvas_width=120,
    canvas_height=3000,
    allow_intersections=False
)
root = diagram.add_right("[bold magenta]Root System[/bold magenta]")
branch1 = root.add_bottom("[cyan]Branch A[/cyan]")
branch2 = root.add_right("[cyan]Branch B[/cyan]")
branch3 = branch2.add_right("[cyan]Branch C[/cyan]")
current = branch1
for i in range(1, 100):
    color = ["green", "yellow", "blue", "red", "magenta"][i % 5]
    current = current.add_bottom(f"[{color}]A-Node-{i}[/{color}]")
current = branch2.add_bottom("[yellow]B-Start[/yellow]")
for i in range(1, 100):
    color = ["cyan", "green", "yellow", "red"][i % 4]
    current = current.add_bottom(f"[{color}]B-Node-{i}[/{color}]")
current = branch3.add_bottom("[blue]C-Start[/blue]")
for i in range(1, 100):
    color = ["blue", "magenta", "cyan", "green"][i % 4]
    current = current.add_bottom(f"[{color}]C-Node-{i}[/{color}]")
mid_node_a = branch1.add_bottom("[red]A-Branch-15[/red]")
sub_a1 = mid_node_a.add_bottom("[green]A-Sub-1[/green]")
sub_a2 = sub_a1.add_bottom("[green]A-Sub-2[/green]")
sub_a3 = sub_a2.add_bottom("[green]A-Sub-3[/green]")
console = Console()

console.print(diagram.render(include_markup=True))
