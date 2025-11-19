import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Optional

from rich.live import Live
from rich.panel import Panel

from asciinode.ascii_diagram import Diagram, Position
from asciinode.errors import DiagramError


MOCK_DELAY_RANGE = (1.0, 2.5)


def _mock_llm_client(messages, **kwargs):
    time.sleep(random.uniform(*MOCK_DELAY_RANGE))
    query = messages[-1]["content"]
    summary = query.strip().split("\n", 1)[0]
    return {
        "choices": [{"message": {"content": f"[MOCK RESPONSE]\n{summary[:200]}..."}}]
    }


def _render(diagram: Diagram, status: str) -> Panel:
    body = diagram.render(include_markup=True)
    return body
    # return Panel(body, title="Penetration Test Live Report", subtitle=status, border_style="cyan")


def _schedule(
    parent,
    query: str,
    *,
    position: Position,
    prompt_override: Optional[str],
    placeholders: list,
) -> "Node":
    node = parent.add(
        "[yellow]⏳ Menunggu jawaban LLM...[/yellow]",
        position,
        llm_answer=False,
    )
    placeholders.append((node, query, prompt_override))
    return node


def main() -> None:
    client = None
    if not os.getenv("FIREWORKS_API_KEY"):
        client = _mock_llm_client

    diagram = Diagram(
        "Penetration Test Report",
        max_box_width=60,
        llm_system_prompt=(
            "You are a cybersecurity analyst. Provide technical, concise Indonesian reports "
            "with clear risk ratings and remediation guidance."
        ),
        llm_client=client,
    )

    mock_scan = """
Starting Nmap 7.93 ( https://nmap.org )
Nmap scan report for staging.infra.local (172.20.5.17)
Host is up (0.048s latency).
Not shown: 994 filtered tcp ports (no-response)
PORT     STATE SERVICE  VERSION
21/tcp   open  ftp      vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_drwxr-xr-x   2 ftp      ftp          4096 Jul  4  2024 drop
80/tcp   open  http     Apache httpd 2.4.49 ((Unix))
|_Potentially vulnerable to CVE-2021-41773 path traversal
135/tcp  open  msrpc    Microsoft Windows RPC
3389/tcp open  ms-wbt-server Microsoft Terminal Services
5985/tcp open  http     Microsoft HTTPAPI httpd 2.0 (SSDP/UPnP)

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
"""

    placeholders = []
    root = diagram.root

    summary_node = _schedule(
        root,
        "Ringkas hasil pemindaian nmap berikut dengan fokus risiko tertinggi:\n"
        + mock_scan,
        position=Position.RIGHT,
        prompt_override=None,
        placeholders=placeholders,
    )

    analysis_node = _schedule(
        summary_node,
        "Jelaskan potensi penyalahgunaan dari layanan yang ditemukan di atas.",
        position=Position.BOTTOM,
        prompt_override=None,
        placeholders=placeholders,
    )

    _schedule(
        analysis_node,
        "Sebutkan kerentanan kritis dan CVE relevan untuk temuan tersebut.",
        position=Position.RIGHT,
        prompt_override=None,
        placeholders=placeholders,
    )

    _schedule(
        analysis_node,
        "Berikan rekomendasi perbaikan prioritas tinggi yang dapat dieksekusi minggu ini.",
        position=Position.LEFT,
        prompt_override=None,
        placeholders=placeholders,
    )

    updates = Queue()

    def worker(node, query, prompt):
        try:
            response = node.diagram._resolve_llm_answer(
                query, {}, llm_system_prompt=prompt
            )
        except DiagramError as exc:
            updates.put((node, f"[red]{exc}[/red]"))
            return
        except Exception as exc:
            updates.put((node, f"[red]LLM error: {exc}[/red]"))
            return
        updates.put((node, response))

    with Live(
        _render(diagram, "Menunggu respons LLM..."), refresh_per_second=8
    ) as live:
        with ThreadPoolExecutor(max_workers=min(4, len(placeholders))) as executor:
            for node, query, prompt in placeholders:
                executor.submit(worker, node, query, prompt)

            completed = 0
            total = len(placeholders)
            while completed < total:
                node, text = updates.get()
                node.text = text
                node.llm_enabled = True
                node.llm_response = text
                live.update(_render(diagram, f"Selesai {completed + 1}/{total}"))
                completed += 1

        live.update(_render(diagram, "Semua respons diterima."))


if __name__ == "__main__":
    main()
