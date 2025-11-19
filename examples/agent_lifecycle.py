from time import sleep
from typing import Dict, cast

from rich.align import Align
from rich.live import Live
from rich.panel import Panel

from asciinode.ascii_diagram import Diagram
from asciinode.diagram_components.node import Node


def _set_state(entry: Dict[str, object], status: str, color: str = "white", icon: str = "•") -> None:
    node = cast(Node, entry["node"])
    title = cast(str, entry["title"])
    node.text = f"{title}\n[{color}]{icon} {status}[/{color}]"


def build_steps(diagram: Diagram):
    steps = []
    ctx: Dict[str, Dict[str, object]] = {}

    def declare_node(key: str, node: Node, title: str, status: str, color: str = "grey50"):
        ctx[key] = {"node": node, "title": title}
        _set_state(ctx[key], status, color=color, icon="○")

    steps.append(("Bootstrapping agent canvas", lambda: None))

    def step_structure():
        core = diagram.add_right("[bold cyan]Orchestrator[/bold cyan]")
        declare_node("input", diagram.add_left("[bold white]Input Gateway[/bold white]"), "Input Gateway", "idle")
        declare_node("analyzer", core.add_top("[bold yellow]Intent Analyzer[/bold yellow]"), "Intent Analyzer", "idle")
        declare_node("planner", core.add_right("[bold green]Planner[/bold green]"), "Planner", "idle")
        declare_node("executor", ctx["planner"]["node"].add_bottom("[bold magenta]Tool Executor[/bold magenta]"), "Tool Executor", "idle")
        declare_node("knowledge", core.add_bottom("[bold blue]Knowledge Base[/bold blue]"), "Knowledge Base", "idle")
        declare_node("output", ctx["planner"]["node"].add_right("[bold white]Response Stream[/bold white]"), "Response Stream", "idle")

        diagram.connect(ctx["input"]["node"], ctx["analyzer"]["node"], label="parse prompt", style="[cyan]")
        diagram.connect(ctx["analyzer"]["node"], ctx["planner"]["node"], label="intent", style="[yellow]")
        diagram.connect(ctx["planner"]["node"], ctx["executor"]["node"], label="plan", style="[green]")
        diagram.connect(ctx["executor"]["node"], ctx["knowledge"]["node"], label="fetch", style="[blue]")
        diagram.connect(ctx["executor"]["node"], ctx["output"]["node"], label="result", style="[magenta]")

        ctx["orchestrator"] = {"node": core, "title": "Agent Orchestrator"}
        _set_state(ctx["orchestrator"], "ready", color="grey66", icon="○")

    steps.append(("Declared agent modules", step_structure))

    def step_ingest():
        _set_state(ctx["input"], "receiving user prompt", color="cyan", icon="▶")
        _set_state(ctx["analyzer"], "queued", color="grey62", icon="…")

    steps.append(("Receiving prompt", step_ingest))

    def step_analysis():
        _set_state(ctx["analyzer"], "extracting intent", color="yellow", icon="⚙")
        _set_state(ctx["knowledge"], "loading memories", color="blue", icon="↺")

    steps.append(("Analyzing context", step_analysis))

    def step_planning():
        _set_state(ctx["planner"], "drafting plan", color="green", icon="✎")
        _set_state(ctx["executor"], "awaiting actions", color="magenta", icon="⌛")

    steps.append(("Planning next actions", step_planning))

    def step_execution():
        _set_state(ctx["executor"], "calling tools", color="magenta", icon="⚡")
        _set_state(ctx["knowledge"], "context injected", color="blue", icon="✔")

    steps.append(("Executing tool calls", step_execution))

    def step_response():
        _set_state(ctx["output"], "streaming reply", color="white", icon="➤")
        _set_state(ctx["input"], "prompt archived", color="green", icon="✔")
        _set_state(ctx["executor"], "tool run complete", color="magenta", icon="✔")

    steps.append(("Delivering response", step_response))

    def step_finalize():
        _set_state(ctx["planner"], "plan history updated", color="green", icon="✔")
        _set_state(ctx["analyzer"], "ready for next", color="yellow", icon="○")
        _set_state(ctx["output"], "channel clear", color="grey66", icon="○")
        _set_state(ctx["orchestrator"], "cycle complete", color="cyan", icon="★")

    steps.append(("Agent cycle complete", step_finalize))

    return steps


def render_panel(diagram: Diagram, message: str) -> Panel:
    body = Align.center(diagram.render(include_markup=True), vertical="middle")
    return Panel(body, title="Agent Live Monitor", subtitle=message, border_style="#888888")


def main():
    diagram = Diagram(
        "Agent Topology",
        vertical_spacing=4,
        horizontal_spacing=6,
        allow_intersections=False,
        connector_style="[#888888]",
    )

    steps = build_steps(diagram)

    with Live(render_panel(diagram, "Initializing"), refresh_per_second=6) as live:
        for message, action in steps:
            action()
            live.update(render_panel(diagram, message))
            sleep(2)


if __name__ == "__main__":
    main()
