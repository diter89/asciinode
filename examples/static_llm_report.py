from __future__ import annotations

import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from rich import print

from asciinode.ascii_diagram import Diagram, Position
from asciinode.diagram_components.node import Node


MOCK_DELAY_RANGE = (1.0, 2.0)


def _mock_llm_client(messages, **kwargs):
    # Simulasikan latensi berbeda untuk tiap permintaan
    time.sleep(random.uniform(*MOCK_DELAY_RANGE))
    query = messages[-1]["content"]
    headline = query.strip().split("\n", 1)[0]
    return {
        "choices": [{"message": {"content": f"[MOCK RESULT]\n{headline[:180]}..."}}]
    }


def _prepare_diagram(
    client,
) -> Tuple[Diagram, List[Tuple[str, Position, Optional[str]]]]:
    diagram = Diagram(
        "Parallel LLM Report",
        # max_box_width=70,
        llm_system_prompt=(
            "You are a cybersecurity analyst. Deliver concise Indonesian findings with risk rating "
            "and remediation guidance."
        ),
        llm_client=client,
    )

    mock_scan = """
Starting Nmap 7.93 ( https://nmap.org )
Nmap scan report for qa.internal.local (10.2.40.12)
Host is up (0.032s latency).
Not shown: 997 closed tcp ports (reset)
PORT     STATE SERVICE  VERSION
22/tcp   open  ssh      OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux; protocol 2.0)
80/tcp   open  http     Apache httpd 2.4.49 ((Unix))
443/tcp  open  ssl/http Apache httpd 2.4.49 ((Unix))
445/tcp  open  microsoft-ds Windows 10 Home 19041 microsoft-ds (workgroup: WORKGROUP)

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
"""

    root = diagram.root
    tasks: List[Tuple[str, Position, Optional[str], Node]] = []

    def schedule(
        parent, prompt: str, position: Position, prompt_override: Optional[str] = None
    ):
        node = parent.add(
            "⏳ pending...",
            position,
            llm_answer=False,
        )
        tasks.append((prompt, position, prompt_override, node))
        return node

    summary_prompt = (
        "Ringkas temuan keamanan dari pemindaian nmap berikut dengan fokus risiko tertinggi:\n"
        + mock_scan
    )
    summary_node = schedule(root, summary_prompt, Position.RIGHT)

    abuse_prompt = "Kamu menggunakan model apa ?"
    abuse_node = schedule(
        summary_node,
        abuse_prompt,
        Position.BOTTOM,
        prompt_override="Answer strictly in English using scientific tone.",
    )

    cve_prompt = "btc naik turun % selama 24 jam"
    schedule(
        abuse_node,
        cve_prompt,
        Position.RIGHT,
        prompt_override="kamu adalah trader terbaik di dunia tugas kamu adalah menganlisa harga btc",
    )

    fix_prompt = "Berikan rekomendasi mitigasi prioritas tinggi yang dapat dilakukan minggu ini berdasarkan temuan tersebut."
    schedule(abuse_node, fix_prompt, Position.LEFT)

    return diagram, tasks


def main() -> None:
    client = None
    if not os.getenv("FIREWORKS_API_KEY"):
        client = _mock_llm_client

    diagram, tasks = _prepare_diagram(client)

    futures = {}
    with ThreadPoolExecutor(max_workers=min(4, len(tasks))) as executor:
        for prompt, _position, prompt_override, node in tasks:
            future = executor.submit(
                diagram._resolve_llm_answer,
                prompt,
                {},
                llm_system_prompt=prompt_override,
            )
            futures[future] = (prompt, node, prompt_override)

        for future in as_completed(futures):
            prompt, node, prompt_override = futures[future]
            try:
                response = future.result()
            except Exception as exc:  # pragma: no cover
                response = f"[red]LLM error: {exc}[/red]"
            node.text = response
            node.llm_enabled = True
            node.llm_query = prompt
            node.llm_response = response
            node.llm_system_prompt = prompt_override

    print(diagram.render(include_markup=True))


if __name__ == "__main__":
    main()
