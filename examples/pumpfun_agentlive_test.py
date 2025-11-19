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
    entry: Dict[str, object],
    status: str,
    *,
    color: str = "white",
    icon: str = "•",
    detail: Optional[str] = None,
) -> None:
    node = cast(Node, entry["node"])
    title = cast(str, entry["title"])
    lines = [title, f"[{color}]{icon} {status}[/{color}]"]
    if detail:
        lines.append(f"[dim]{detail}[/dim]")
    node.text = "\n".join(lines)


def _declare(ctx: Dict[str, Dict[str, object]], key: str, node: Node, title: str, status: str) -> None:
    ctx[key] = {"node": node, "title": title}
    _set_state(ctx[key], status, color="grey58", icon="○")


def build_structure(diagram: Diagram) -> Dict[str, Dict[str, object]]:
    ctx: Dict[str, Dict[str, object]] = {}

    root = diagram.root
    root.text = "[bold cyan]Pumpfun Workflow[/bold cyan]"

    intake = root.add_right("[bold white]Prompt Intake[/bold white]")
    parser = intake.add_right("[bold yellow]Intent Parser[/bold yellow]")
    transformer = parser.add_right("[bold green]Pumpfun NL2JSON[/bold green]")
    validator = transformer.add_right("[bold magenta]Result Normalizer[/bold magenta]")
    output = validator.add_right("[bold blue]Delivery Channel[/bold blue]")

    env = parser.add_bottom("[bold cyan]Environment Check[/bold cyan]")
    telemetry = transformer.add_bottom("[bold white]Telemetry[/bold white]")

    diagram.connect(env, transformer, label="config", style="[cyan]")
    diagram.connect(transformer, telemetry, label="metrics", style="[blue]")

    ctx["orchestrator"] = {"node": root, "title": "Pumpfun Workflow"}
    _set_state(ctx["orchestrator"], "idle", color="grey66", icon="○")

    _declare(ctx, "intake", intake, "Prompt Intake", "waiting")
    _declare(ctx, "parser", parser, "Intent Parser", "standby")
    _declare(ctx, "env", env, "Environment Check", "pending")
    _declare(ctx, "transformer", transformer, "Pumpfun NL2JSON", "standby")
    _declare(ctx, "validator", validator, "Result Normalizer", "standby")
    _declare(ctx, "output", output, "Delivery Channel", "standby")
    _declare(ctx, "telemetry", telemetry, "Telemetry", "standby")

    return ctx


def render_frame(diagram: Diagram, message: str):
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

    ctx = build_structure(diagram)
    analysis_container: Dict[str, Any] = {}
    error_holder: Dict[str, Exception] = {}

    steps = []

    steps.append(("Initializing agent", lambda: _set_state(ctx["orchestrator"], "boot", color="cyan", icon="▶")))

    def step_prompt():
        snippet = shorten(prompt, width=80, placeholder="…")
        _set_state(ctx["intake"], "received", color="cyan", icon="✉", detail=snippet)
        _set_state(ctx["parser"], "queued", color="yellow", icon="…")

    steps.append(("Receiving prompt", step_prompt))

    def step_env():
        if os.getenv("FIREWORKS_API_KEY"):
            _set_state(ctx["env"], "ready", color="cyan", icon="✔", detail="FIREWORKS_API_KEY")
            _set_state(ctx["telemetry"], "API key detected", color="green", icon="✔")
        else:
            _set_state(ctx["env"], "missing key", color="red", icon="✖", detail="Set FIREWORKS_API_KEY")
            _set_state(ctx["telemetry"], "missing FIREWORKS_API_KEY", color="red", icon="✖")
            error_holder["env"] = RuntimeError("FIREWORKS_API_KEY environment variable is missing")

    steps.append(("Validating environment", step_env))

    def step_intent():
        if error_holder:
            _set_state(ctx["parser"], "skipped", color="red", icon="⚠", detail="Environment error")
            return
        _set_state(ctx["parser"], "extracting", color="yellow", icon="⚙")
        _set_state(ctx["transformer"], "waiting", color="green", icon="⌛")

    steps.append(("Parsing intent", step_intent))

    def step_transform():
        if error_holder:
            return
        try:
            _set_state(ctx["transformer"], "calling API", color="green", icon="⚡")
            analysis = generate_analysis(prompt, return_raw=return_raw)
            analysis_container["response"] = analysis
            _set_state(ctx["transformer"], "completed", color="green", icon="✔")
        except Exception as exc:  # noqa: BLE001
            _set_state(ctx["transformer"], "failed", color="red", icon="✖", detail=str(exc)[:70])
            error_holder["call"] = exc

    steps.append(("Generating analysis", step_transform))

    def step_normalize():
        if error_holder:
            _set_state(ctx["validator"], "skipped", color="red", icon="⚠")
            return
        try:
            parsed = analysis_container["response"].parser()
            analysis_container["parsed"] = parsed
            action = parsed.get("action", "unknown")
            returned = parsed.get("meta", {}).get("returned")
            detail = f"action={action}"
            if returned is not None:
                detail += f" • returned={returned}"
            _set_state(ctx["validator"], "normalized", color="magenta", icon="✔", detail=detail)
        except Exception as exc:  # noqa: BLE001
            _set_state(ctx["validator"], "failed", color="red", icon="✖", detail=str(exc)[:70])
            error_holder["parse"] = exc

    steps.append(("Normalizing result", step_normalize))

    def step_output():
        if error_holder:
            _set_state(ctx["output"], "aborted", color="red", icon="✖")
            return
        parsed = cast(Dict[str, Any], analysis_container.get("parsed", {}))
        action = parsed.get("action", "unknown")
        meta = parsed.get("meta", {})
        returned = meta.get("returned") or meta.get("fetched")
        detail = f"action={action}"
        if returned is not None:
            detail += f" • {returned} items"
        _set_state(ctx["output"], "ready", color="blue", icon="➤", detail=detail)
        _set_state(ctx["telemetry"], "success", color="green", icon="★")
        _set_state(ctx["orchestrator"], "complete", color="cyan", icon="★")

    steps.append(("Delivering response", step_output))

    with Live(render_frame(diagram, "Booting"), refresh_per_second=6) as live:
        for message, action in steps:
            action()
            live.update(render_frame(diagram, message))
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
