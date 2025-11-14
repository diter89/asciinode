import json
import sys
from typing import Optional

from rich import print

from asciinode.agent.fireworks_client import FireworksError, chat_completion
from asciinode.ascii_diagram import generate_diagram


def build_prompt(args: Optional[list[str]]) -> str:
    if args:
        return " ".join(args)
    return "Draw what I'm thinking: user → frontend → api → database"


def logging_client(*args, **kwargs):
    response = chat_completion(*args, **kwargs)
    print("[yellow]\nRaw Fireworks response:[/]")
    print(json.dumps(response, indent=2))
    return response


def main() -> None:
    prompt = build_prompt(sys.argv[1:])
    print(f"[bold cyan]Prompt:[/] {prompt}\n")
    try:
        diagram = generate_diagram(prompt, client=logging_client)
    except FireworksError as exc:
        print(f"[red]Fireworks API error:[/] {exc}")
        return
    except ValueError as exc:
        print(f"[red]Failed to parse LLM response:[/] {exc}")
        return

    print(diagram.render(include_markup=True))


if __name__ == "__main__":
    main()
