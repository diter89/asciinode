import argparse
import json
import os
from textwrap import shorten
from time import sleep
from typing import Any, Dict, Optional, cast

from pumpfun_nl2json import generate_analysis
from rich.align import Align
from rich.console import Console
from rich.live import Live

from asciinode.ascii_diagram import Diagram
from asciinode.diagram_components.node import Node


console = Console()


def _set_state(
    node: Node,
    title: str,
    status: Optional[str] = None,
    *,
    color: str = "white",
    icon: str = "•",
    detail: Optional[str] = None,
) -> None:
    lines = [title]
    if status is not None:
        lines.append(f"[{color}]{icon} {status}[/{color}]")
    if detail:
        lines.append(f"[dim]{detail}[/dim]")
    node.text = "\n".join(lines)


def render_panel(diagram: Diagram, message: str):
    content = f"[bold cyan]{message}[/bold cyan]\n\n{diagram.render(include_markup=True)}"
    return Align.center(content, vertical="middle")


def _print_json_block(title: str, data: Any) -> None:
    if data is None:
        return
    console.print(f"\n[bold underline]{title}[/bold underline]")
    try:
        console.print_json(data=data)
    except Exception:
        console.print(data)


def run_workflow(prompt: str, *, delay: float, return_raw: bool) -> None:
    diagram = Diagram(
        "Pumpfun Workflow",
        vertical_spacing=4,
        horizontal_spacing=6,
        allow_intersections=False,
        connector_style="[#888888]",
    )

    ctx: Dict[str, Node] = {}
    analysis_container: Dict[str, Any] = {}
    error_holder: Dict[str, Exception] = {}

    steps = []

    def step_boot():
        root = diagram.root
        ctx["root"] = root
        _set_state(root, "[bold cyan]Pumpfun Workflow[/bold cyan]", "booting", color="cyan", icon="▶")

    steps.append(("Initializing canvas", step_boot))

    def step_prompt():
        snippet = shorten(prompt, width=80, placeholder="…")
        intake = ctx["root"].add_right("[bold white]Prompt Intake[/bold white]")
        ctx["intake"] = intake
        _set_state(intake, "[bold white]Prompt Intake[/bold white]", "received", color="cyan", icon="✉", detail=snippet)

    steps.append(("Receiving prompt", step_prompt))

    def step_parser():
        parser = ctx["intake"].add_right("[bold yellow]Intent Parser[/bold yellow]")
        ctx["parser"] = parser
        _set_state(parser, "[bold yellow]Intent Parser[/bold yellow]", "queued", color="yellow", icon="…")

    steps.append(("Queueing intent parser", step_parser))

    def step_env():
        env = ctx["parser"].add_bottom("[bold cyan]Environment Check[/bold cyan]")
        ctx["env"] = env
        key = os.getenv("FIREWORKS_API_KEY")
        if key:
            _set_state(env, "[bold cyan]Environment Check[/bold cyan]", "ready", color="cyan", icon="✔", detail="FIREWORKS_API_KEY")
        else:
            _set_state(env, "[bold cyan]Environment Check[/bold cyan]", "missing", color="red", icon="✖", detail="Set FIREWORKS_API_KEY")
            error_holder["env"] = RuntimeError("FIREWORKS_API_KEY environment variable is missing")

    steps.append(("Validating environment", step_env))

    def step_generator():
        generator = ctx["parser"].add_right("[bold green]Pumpfun NL2JSON[/bold green]")
        ctx["generator"] = generator
        _set_state(generator, "[bold green]Pumpfun NL2JSON[/bold green]", "waiting", color="green", icon="⌛")
        if "env" in ctx:
            diagram.connect(ctx["env"], generator, label="config", style="[cyan]")

        telemetry = generator.add_bottom("[bold white]Telemetry[/bold white]")
        ctx["telemetry"] = telemetry
        _set_state(telemetry, "[bold white]Telemetry[/bold white]", "pending", color="grey58", icon="○")

    steps.append(("Preparing LLM bridge", step_generator))

    def step_outputs():
        validator = ctx["generator"].add_right("[bold magenta]Result Normalizer[/bold magenta]")
        ctx["validator"] = validator
        _set_state(validator, "[bold magenta]Result Normalizer[/bold magenta]", "pending", color="magenta", icon="○")

        output = validator.add_right("[bold blue]Delivery Channel[/bold blue]")
        ctx["output"] = output
        _set_state(output, "[bold blue]Delivery Channel[/bold blue]", "pending", color="blue", icon="○")

    steps.append(("Staging normalization pipeline", step_outputs))

    def step_analysis():
        if "env" in error_holder:
            _set_state(ctx["generator"], "[bold green]Pumpfun NL2JSON[/bold green]", "blocked", color="red", icon="✖", detail="Missing API key")
            _set_state(ctx["validator"], "[bold magenta]Result Normalizer[/bold magenta]", "skipped", color="red", icon="⚠")
            _set_state(ctx["output"], "[bold blue]Delivery Channel[/bold blue]", "aborted", color="red", icon="✖")
            _set_state(ctx["telemetry"], "[bold white]Telemetry[/bold white]", "no credentials", color="red", icon="✖")
            _set_state(ctx["root"], "[bold cyan]Pumpfun Workflow[/bold cyan]", "blocked", color="red", icon="✖")
            return

        try:
            _set_state(ctx["generator"], "[bold green]Pumpfun NL2JSON[/bold green]", "calling", color="green", icon="⚡")
            analysis = generate_analysis(prompt, return_raw=return_raw)
            analysis_container["response"] = analysis
            _set_state(ctx["generator"], "[bold green]Pumpfun NL2JSON[/bold green]", "completed", color="green", icon="✔")
            _set_state(ctx["telemetry"], "[bold white]Telemetry[/bold white]", "success", color="green", icon="★")
        except Exception as exc:  # noqa: BLE001
            _set_state(ctx["generator"], "[bold green]Pumpfun NL2JSON[/bold green]", "failed", color="red", icon="✖", detail=str(exc)[:70])
            _set_state(ctx["telemetry"], "[bold white]Telemetry[/bold white]", "error", color="red", icon="✖")
            error_holder["call"] = exc
            return

        try:
            parsed = analysis_container["response"].parser()
        except Exception as exc:  # noqa: BLE001
            _set_state(ctx["validator"], "[bold magenta]Result Normalizer[/bold magenta]", "failed", color="red", icon="✖", detail=str(exc)[:70])
            _set_state(ctx["output"], "[bold blue]Delivery Channel[/bold blue]", "aborted", color="red", icon="✖")
            error_holder["parse"] = exc
            return

        analysis_container["parsed"] = parsed
        action = parsed.get("action", "unknown")
        meta = parsed.get("meta", {})
        returned = meta.get("returned")
        detail = f"action={action}"
        if returned is not None:
            detail += f" • returned={returned}"
        _set_state(ctx["validator"], "[bold magenta]Result Normalizer[/bold magenta]", "normalized", color="magenta", icon="✔", detail=detail)

        total = returned if returned is not None else meta.get("fetched")
        output_detail = f"action={action}"
        if total is not None:
            output_detail += f" • {total} items"
        _set_state(ctx["output"], "[bold blue]Delivery Channel[/bold blue]", "ready", color="blue", icon="➤", detail=output_detail)
        _set_state(ctx["root"], "[bold cyan]Pumpfun Workflow[/bold cyan]", "complete", color="green", icon="★")

    steps.append(("Running analysis", step_analysis))

    with Live(render_panel(diagram, "Booting"), refresh_per_second=6) as live:
        for message, action in steps:
            action()
            live.update(render_panel(diagram, message))
            if delay:
                sleep(delay)

    if error_holder:
        console.print("\n[bold red]Workflow terminated due to error.[/bold red]")
        for key, exc in error_holder.items():
            console.print(f" • {key}: {exc}")
        return

    parsed = cast(Dict[str, Any], analysis_container.get("parsed", {}))
    if not parsed:
        console.print("\n[bold yellow]No parsed payload available.[/bold yellow]")
        return

    console.print("\n[bold underline]Structured Result Summary[/bold underline]")
    action = parsed.get("action")
    if action:
        console.print(f"Action: [green]{action}[/green]")

    meta = parsed.get("meta", {})
    if meta:
        console.print(f"Meta: {meta}")

    _print_json_block("Parsed Payload", parsed)

    raw_payload = None
    if hasattr(analysis_container.get("response"), "raw"):
        try:
            raw_payload = analysis_container["response"].raw()
        except Exception:  # noqa: BLE001
            raw_payload = None

    if raw_payload:
        llm_content = (
            raw_payload.get("raw_llm_response", {}).get("content")
            if isinstance(raw_payload, dict)
            else None
        )
        if llm_content:
            console.print("\n[bold underline]LLM Parser Instruction[/bold underline]")
            try:
                console.print_json(data=json.loads(llm_content))
            except Exception:
                console.print(llm_content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pumpfun NL + ASCIINODE agent workflow demo")
    parser.add_argument("prompt", help="Natural language Pumpfun request")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Delay between workflow steps (seconds)",
    )
    parser.add_argument(
        "--return-raw",
        action="store_true",
        help="Request raw Fireworks metadata from pumpfun_nl2json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_workflow(args.prompt, delay=max(args.delay, 0.0), return_raw=args.return_raw)


if __name__ == "__main__":
    main()
