from time import sleep

from rich.align import Align
from rich.live import Live
from rich.panel import Panel

from asciinode.ascii_diagram import Diagram as _basediagram


class Diagram(_basediagram):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("connector_style", "[red bold]")
        super().__init__(*args, **kwargs)

def build_steps(diagram: Diagram):
    steps = []
    ctx: dict[str, object] = {}

    steps.append(("Starting n8n workflow canvas", lambda: None))

    def step_trigger():
        ctx["trigger"] = diagram.add_right("[bold green]HTTP Trigger[/bold green]\n/webhook")

    steps.append(("Added HTTP trigger", step_trigger))

    def step_parser():
        trigger = ctx["trigger"]
        ctx["parser"] = trigger.add_right("[cyan]Transform JSON[/cyan]\n(clean payload)")

    steps.append(("Parsing incoming payload", step_parser))

    def step_router():
        parser = ctx["parser"]
        ctx["router"] = parser.add_right("[bold yellow]Route by Priority[/bold yellow]\n(IF / SWITCH)")

    steps.append(("Inserted routing logic", step_router))

    def step_branch_notifications():
        router = ctx["router"]
        ctx["slack"] = router.add_bottom("[bold magenta]Slack Notify[/bold magenta]")
        ctx["email"] = ctx["slack"].add_bottom("[blue]Email Escalation[/blue]")

    steps.append(("Added notification branch", step_branch_notifications))

    def step_branch_records():
        router = ctx["router"]
        ctx["crm"] = router.add_right("[bold cyan]CRM Update[/bold cyan]\n(Salesforce)")
        ctx["db"] = router.add_top("[white]PostgreSQL Archive[/white]")

    steps.append(("Added data sync branches", step_branch_records))

    def step_operations_layer():
        ctx["ops"] = diagram.add_top("[bold orange]Ops Dashboard[/bold orange]")
        ctx["incident"] = ctx["ops"].add_bottom("[bold red]Incident Manager[/bold red]")

    steps.append(("Added operations monitor", step_operations_layer))

    def step_cross_links():
        diagram.connect(ctx["trigger"], ctx["ops"], label="heartbeat")
        diagram.connect(ctx["incident"], ctx["slack"], label="urgent ping")
        diagram.connect(ctx["crm"], ctx["db"], label="record id")
        diagram.connect(ctx["email"], ctx["crm"], label="handoff")

    steps.append(("Linked cross-node flows", step_cross_links))

    def step_finish():
        footer = diagram.root.add_bottom("[bold]Workflow Complete[/bold]")
        footer.add_bottom("[dim]Ready for production[/dim]")

    steps.append(("Finalized workflow summary", step_finish))

    return steps


def render_panel(diagram: Diagram, message: str) -> Panel:
    body = Align.center(diagram.render(include_markup=True), vertical="middle")
    return Panel(body, title="n8n Live Builder", subtitle=message, border_style="bright_magenta")

def main():
    diagram = Diagram(
        "n8n Workflow",
        vertical_spacing=4,
        horizontal_spacing=6,
        allow_intersections=False,
    )

    steps = build_steps(diagram)

    with Live(render_panel(diagram, "Initializing"), refresh_per_second=6) as live:
        for message, action in steps:
            action()
            live.update(render_panel(diagram, message))
            sleep(0.9)


if __name__ == "__main__":
    main()
