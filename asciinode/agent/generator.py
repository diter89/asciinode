import json
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from ..diagram_components.core import Position
from ..diagram_components.diagram import Diagram
from ..diagram_components.node import Node
from .fireworks_client import chat_completion
from .schema import DiagramInstruction, EdgeInstruction, NodeInstruction

Message = Mapping[str, Any]
ChatClient = Callable[..., Dict[str, Any]]


_SCHEMA_TEXT = (
    '{"title": optional string, '
    '"nodes": [{"id": str, "text": str, "parent": optional str, '
    '"position": one of top/right/bottom/left}], '
    '"edges": [{"source": str, "target": str, "label": optional str, "style": optional str}]}'
)

SYSTEM_PROMPT = (
    "You are an assistant that renders ASCII node diagrams. "
    "Return ONLY JSON following this schema: "
    + _SCHEMA_TEXT
)


def _build_messages(prompt: str) -> List[Message]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


def _build_diagram(instruction: DiagramInstruction) -> Diagram:
    title = instruction.title or "Diagram"
    diagram = Diagram(title)
    id_to_node: Dict[str, Node] = {"root": diagram.root}

    for node_inst in instruction.nodes:
        parent = id_to_node.get(node_inst.parent_id or "root")
        if parent is None:
            raise ValueError(f"Parent id '{node_inst.parent_id}' does not exist for node '{node_inst.node_id}'.")

        node = _attach_node(parent, node_inst)
        id_to_node[node_inst.node_id] = node

    for edge in instruction.edges:
        source = id_to_node.get(edge.source_id)
        target = id_to_node.get(edge.target_id)
        if source is None or target is None:
            raise ValueError(f"Edge references unknown node: {edge}")
        diagram.connect(source, target, label=edge.label, style=edge.style)

    return diagram


def _attach_node(parent: Node, instruction: NodeInstruction) -> Node:
    if instruction.position == Position.TOP:
        return parent.add_top(instruction.text)
    if instruction.position == Position.BOTTOM:
        return parent.add_bottom(instruction.text)
    if instruction.position == Position.LEFT:
        return parent.add_left(instruction.text)
    if instruction.position == Position.RIGHT:
        return parent.add_right(instruction.text)
    return parent.add(instruction.text)


def _parse_instruction(content: str) -> DiagramInstruction:
    content = content.strip()
    if not content:
        raise ValueError("LLM response is empty.")

    content = re.sub(r"```(?:json)?", "", content, flags=re.IGNORECASE).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = content[start : end + 1]
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                raise ValueError(f"LLM response is not valid JSON: {exc}") from exc
        else:
            raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("LLM response JSON must be an object.")

    return DiagramInstruction.from_dict(data)


def generate_diagram(
    prompt: str,
    *,
    client: ChatClient = chat_completion,
    client_kwargs: Optional[Dict[str, Any]] = None,
) -> Diagram:
    messages = _build_messages(prompt)
    payload_kwargs = client_kwargs or {}
    response = client(messages, **payload_kwargs)

    choices = response.get("choices")
    if not isinstance(choices, Iterable) or not choices:
        raise ValueError("Fireworks response missing choices.")

    first_choice = next(iter(choices))
    if not isinstance(first_choice, Mapping):
        raise ValueError("Invalid choice structure from Fireworks.")

    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Fireworks choice missing message content.")

    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Fireworks message content must be a string containing JSON.")

    instruction = _parse_instruction(content)
    return _build_diagram(instruction)
