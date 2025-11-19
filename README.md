# asciinode

Utilities for composing and rendering ASCII node diagrams in Python, with optional helpers to drive diagram creation from LLM responses.

> **Note**
>
> The project is distributed under the MIT License and provided as-is without warranty. Examples and APIs may evolve; updates are not guaranteed to stay in sync with external services.

## Installation

```bash
pip install .
```

## Usage

### Manual diagram building

```python
from asciinode.ascii_diagram import Diagram

diagram = Diagram("Service Topology")
api = diagram.add_right("API Gateway")
worker = api.add_bottom("Worker Pool")
store = worker.add_bottom("Data Store")

# Optional titles show up on the box border
api.title = "Layer 1"
worker.title = "Compute"
store.title = "Storage"

diagram.connect(api, worker, label="dispatch")
diagram.connect(worker, store, label="persist")

print(diagram.render(include_markup=True))

# Validate structure (returns [] when everything is consistent)
print(diagram.validate())

# Render only the worker branch
print(diagram.render_subtree(worker))
```

### Generating diagrams from an LLM

```python
from asciinode.agent import generate_diagram

prompt = "User request flows through frontend -> api -> database"
diagram = generate_diagram(prompt)
print(diagram.render(include_markup=True))
```
Set the Fireworks API key before running the LLM helper:

```bash
export FIREWORKS_API_KEY="fw_xxx"
```

### Embedding LLM answers inside existing diagrams

Use the high-level `add_llm_answer()` helper to replace any node text with the live response from your LLM client. The helper automatically sets `llm_answer=True` and accepts the usual positioning helpers plus an optional per-node system prompt.

```python
from asciinode.ascii_diagram import Diagram, Position

diagram = Diagram(
    "Security Overview",
    llm_system_prompt=(
        "You are a cybersecurity analyst. Provide concise Indonesian answers with clear risk and mitigation notes."
    ),
)

root = diagram.root

summary = root.add_llm_answer(
    "Ringkas hasil pemindaian nmap berikut dengan fokus risiko tertinggi:",
    position=Position.RIGHT,
)

analysis = summary.add_llm_answer(
    "Sebutkan CVE paling kritis dan jelaskan risikonya.",
    position=Position.BOTTOM,
    llm_system_prompt="Beri jawaban ringkas dalam bahasa Indonesia dengan bullet list.",
)

notes = analysis.add_left(
    "Catatan manual",
    llm_answer=False,  # ordinary text node, not replaced by the LLM
)

print(diagram.render(include_markup=True))
```

> **Tip**
>
> If you prefer the lower-level API, every `add_*()` method still accepts `llm_answer=True`, `llm_query=...`, and `llm_system_prompt=...` through keyword arguments. The `add_llm_answer()` convenience wrapper simply applies those flags for you.

#### Using the lower-level API directly

For advanced scenarios—such as reusing a single node for multiple queries, or injecting custom metadata—you can interact with the base `add_*()` methods manually. Provide the `llm_answer=True` flag and any overrides you need.

```python
from asciinode.ascii_diagram import Diagram, Position

diagram = Diagram("Threat Brief")

node = diagram.add_right(
    "Initial prompt",  # will be replaced
    llm_answer=True,
    llm_query="Summarize the top three network risks in English.",
    llm_system_prompt="You are a SOC analyst. Respond with a numbered list in English.",
)

follow_up = node.add_bottom(
    "Detail follow-up",  # also replaced via LLM
    llm_answer=True,
    llm_query="For each risk above, give a mitigation in one sentence.",
)

manual_note = follow_up.add_left(
    "Analyst note: verify mitigations",  # regular node, not LLM-backed
)

print(diagram.render(include_markup=True))
```

This approach gives you full control over prompts, system overrides, and when a node should remain plain text. The resulting diagram still records the original query (`node.llm_query`) and system prompt (`node.llm_system_prompt`) for later inspection.

### Combined workflow demonstration

```python
from rich import print
from typing import Callable

from asciinode.ascii_diagram import Diagram as _BaseDiagram


class Diagram(_BaseDiagram):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("connector_style", "[#888888 bold]")
        super().__init__(*args, **kwargs)


def traceroute_analysis() -> Diagram:
    diagram = Diagram("Start: Your Network")

    hop1 = diagram.add_right("Hop 1: Gateway\n3.8ms")
    hop3 = hop1.add_right("Hop 3: ISP Entry\n23.0ms")
    hop4 = hop3.add_right("Hop 4-8: ISP Network\n24-69ms")

    hop1.add_bottom("Hop 2: Timeout\n* * *")
    hop4.add_bottom("Hop 9-10: Timeout\n* * *")

    hop11 = hop4.add_right("Hop 11: Google Edge\n35.6ms")
    hop15 = hop11.add_right("Hop 12-15: Google Internal\n29-50ms")
    hop15.add_bottom("Hop 16-24: Timeout\n* * *")
    hop15.add_right("Hop 25: Google.com\n67.7ms\nSUCCESS!")

    return diagram


def complex_network() -> Diagram:
    diagram = Diagram("Main Router", allow_intersections=True, max_layout_width=60)

    firewall = diagram.add_bottom("Firewall")
    load_balancer = firewall.add_bottom("Load Balancer")

    web_server1 = load_balancer.add_right("Web Server 1")
    web_server2 = load_balancer.add_right("Web Server 2")
    web_server3 = load_balancer.add_right("Web Server 3")

    app_server1 = web_server1.add_bottom("App Server 1")
    app_server2 = web_server2.add_bottom("App Server 2")
    app_server3 = web_server3.add_bottom("App Server 3")

    primary_db = app_server1.add_bottom("Primary DB\nMySQL")
    replica_db = app_server2.add_bottom("Replica DB\nMySQL")
    app_server3.add_bottom("Backup DB\nMySQL")

    primary_db.add_right("Redis Cache")
    replica_db.add_right("File Storage\nS3")

    monitoring = diagram.add_left("Monitoring\nPrometheus")
    logging = diagram.add_right("Logging\nELK Stack")

    monitoring.add_bottom("Web Monitor")
    monitoring.add_bottom("App Monitor")
    monitoring.add_bottom("DB Monitor")

    return diagram


def nmap_workflow() -> Diagram:
    diagram = Diagram("Start Nmap")
    diagram.add_right("Host Discovery\nnmap -sn")
    diagram.add_bottom("Port Scanning\nnmap -sS")
    diagram.add_left("Service Detection\nnmap -sV")
    diagram.add_bottom("OS Detection\nnmap -O")
    diagram.add_right("Vulnerability Scan\nnmap --script vuln")
    diagram.add_left("Generate Report\nnmap -oN report")
    diagram.add_bottom("Cleanup")
    return diagram


def simple_tree() -> Diagram:
    diagram = Diagram("Server")
    diagram.add("Layanan 1")
    diagram.add("Layanan 2")
    return diagram


def complex_tree() -> Diagram:
    diagram = Diagram("Root")
    node1 = diagram.add("Child 1")
    node1.add("Grandchild 1")
    node1.add("Grandchild 2")
    diagram.add("Child 2")
    return diagram


def multiple_positions() -> Diagram:
    diagram = Diagram("Main Server")
    diagram.add_right("Database")
    diagram.add_bottom("API Gateway")
    diagram.add_left("Cache")
    return diagram.render(include_markup=True)


def multi_level() -> Diagram:
    diagram = Diagram("Load Balancer")
    srv1 = diagram.add("Server 1")
    srv1.add_right("DB Master")
    srv1.add_left("Redis")
    srv2 = diagram.add("Server 2")
    srv2.add_right("DB Slave")
    srv2.add_left("Cache Mirror").add_top("[red]hello[/red]")
    return diagram.render(include_markup=True)


def print_example(title: str, builder: Callable[[], Diagram]) -> None:
    print(title)
    print(builder())
    print()


def main() -> None:
    print_example("Traceroute Analysis", traceroute_analysis)
    print_example("Complex Network - Fixed API", complex_network)
    print_example("Nmap Workflow - Crazy Directions", nmap_workflow)
    print_example("Example 1: Simple Tree", simple_tree)
    print_example("Example 2: Complex Tree", complex_tree)
    print_example("Example 3: Multiple Positions", multiple_positions)
    print_example("Example 4: Multi-level", multi_level)


if __name__ == "__main__":
    main()
```

Sample output excerpt:

```
Traceroute Analysis
╭────────────╮    ╭────────────╮    ╭────────────╮    ╭────────────╮    ╭────────────╮    ╭────────────╮    ╭────────────╮
│ Start: You │    │ Hop 1: Gat │    │ Hop 3: ISP │    │ Hop 4-8: I │    │ Hop 11: Go │    │ Hop 12-15: │    │ Hop 25: Go │
│ r Network  │───►│    eway    │───►│    Entry   │───►│ SP Network │───►│ ogle Edge  │──╮ │  Google In │    │  ogle.com  │
╰────────────╯    │   3.8ms    │    │   23.0ms   │    │  24-69ms   │    │   35.6ms   │  ╰►│   ternal   │───►│   67.7ms   │
                  ╰────────────╯    ╰────────────╯    ╰────────────╯    ╰────────────╯    │  29-50ms   │    │  SUCCESS!  │
                         │                                   │                            ╰────────────╯    ╰────────────╯
                         │                                   │                                   │
                         │                                   │                                   │
                         ▼                                   ▼                                   │
                  ╭────────────╮                      ╭────────────╮                             ▼
                  │ Hop 2: Tim │                      │ Hop 9-10:  │                      ╭────────────╮
                  │    eout    │                      │  Timeout   │                      │ Hop 16-24: │
                  │   * * *    │                      │   * * *    │                      │   Timeout  │
                  ╰────────────╯                      ╰────────────╯                      │   * * *    │
                                                                                          ╰────────────╯


Simple Tree
          ╭────────╮
          │ Server │
          ╰────────╯
               │
      ╭────────┼───────╮
      │                │
      ▼                ▼
╭───────────╮    ╭───────────╮
│ Layanan 1 │    │ Layanan 2 │
╰───────────╯    ╰───────────╯

Complex Tree
                     ╭──────╮
                     │ Root │
                     ╰──────╯
                         │
                  ╭──────┼───────────────────╮
                  │                          │
                  ▼                          ▼
             ╭─────────╮                ╭─────────╮
             │ Child 1 │                │ Child 2 │
             ╰─────────╯                ╰─────────╯
                  │
        ╭─────────┼─────────╮
        │                   │
        ▼                   ▼
╭──────────────╮    ╭──────────────╮
│ Grandchild 1 │    │ Grandchild 2 │
╰──────────────╯    ╰──────────────╯

Multiple Positions
╭───────╮    ╭─────────────╮    ╭──────────╮
│ Cache │ ◄──│ Main Server │───►│ Database │
╰───────╯    ╰─────────────╯    ╰──────────╯
                    │
                    │
                    │
                    ▼
             ╭─────────────╮
             │ API Gateway │
             ╰─────────────╯

Multi-level
                ╭───────────────╮
                │ Load Balancer │
                ╰───────────────╯
                        │
                      ╭─┤
                      │ │
                      ▼ │
   ╭───────╮    ╭───────┼──╮    ╭───────────╮
   │ Redis │ ◄──│ Server│1 │───►│ DB Master │
   ╰───────╯    ╰───────┼──╯    ╰───────────╯
    ╭───────╮           │
    │ hello │           │
    ╰───────╯           │
        ▲               │
        │               │
        │               ├─╮
        │                 │
        │                 ▼
╭──────────────╮    ╭──────────╮    ╭──────────╮
│ Cache Mirror │ ◄──│ Server 2 │───►│ DB Slave │
╰──────────────╯    ╰──────────╯    ╰──────────╯


```
## Examples

Comprehensive examples demonstrating various features are available in the `examples/` directory:

- **Basic Examples**: `basic_example.py`, `main_demo.py`, `simple_grid.py`
- **Architecture Diagrams**: `omnichannel_architecture_diagram.py`, `advanced_tree_connections.py`
- **LLM Integration**: `live_llm_report.py`, `static_llm_report.py`, `pumpfun_agent_workflow.py`
- **Advanced Features**: `diagram_diff_example.py`, `diagram_validate_example.py`, `automation_flow.py`
- **Specialized Tools**: `neofetch.py`, `monitoring.py`, `crypto_map.py`

Run examples with:
```bash
cd examples
python3 basic_example.py
python3 pumpfun_agent_workflow.py "coin pepe"
```

See `examples/README.md` for detailed descriptions and categories.

## License

This project is licensed under the MIT License. You are free to use, modify, and distribute the code. The software is provided "as is" without warranty of any kind, and there is no guarantee of future updates or maintenance.
