"""OpenAI-compatible tool schemas — the same operations the MCP server exposes.

Keeping them side by side makes the "agent only talks to tools" rule visible in
one file: if a tool is added to `mcp_server`, it shows up here too.

The MCP server takes the caller identity explicitly (`user_id`, `role`) because
MCP carries no HTTP session. The chat agent does have one, so its schemas carry
**no identity parameters at all**: the actor is injected by `execute_tool_call`.
Exposing `user_id` to the model made it ask the user "назовите ваш user_id".
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.errors import ValidationError


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    _tool(
        "absence_create",
        "Создать черновик заявки на отсутствие (отгул, отпуск, больничный).",
        {
            "type": {"type": "string", "enum": ["day_off", "vacation", "sick"]},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "reason": {"type": "string"},
        },
        ["type", "date_from", "date_to"],
    ),
    _tool(
        "absence_status",
        "Показать статус заявки на отсутствие.",
        {"request_id": {"type": "integer"}},
        ["request_id"],
    ),
    _tool(
        "absence_list",
        "Список заявок на отсутствие: свои или подопечных/команды.",
        {},
        [],
    ),
    _tool(
        "checklist_get",
        "Чек-лист адаптации с прогрессом.",
        {},
        [],
    ),
    _tool(
        "checklist_complete",
        "Отметить пункт чек-листа выполненным (или снять отметку).",
        {"item_id": {"type": "integer"}},
        ["item_id"],
    ),
    _tool(
        "contacts_lookup",
        "Найти, к кому обратиться по вопросу (наставник, руководитель, HR BP).",
        {"query": {"type": "string"}},
        [],
    ),
    _tool(
        "contacts_route",
        "Маршрутизировать вопрос: вернуть следующего по цепочке эскалации, "
        "если база знаний не отвечает.",
        {"question": {"type": "string"}},
        ["question"],
    ),
]

TOOL_NAMES: frozenset[str] = frozenset(schema["function"]["name"] for schema in TOOL_SCHEMAS)

# OpenAI function names cannot carry dots; the action layer (and the MCP server)
# names the same operations `absence.create`, `checklist.get`, …
TOOL_TO_ACTION: dict[str, str] = {
    "absence_create": "absence.create",
    "absence_status": "absence.status",
    "absence_list": "absence.list",
    "checklist_get": "checklist.get",
    "checklist_complete": "checklist.complete",
    "contacts_lookup": "contacts.lookup",
    "contacts_route": "contacts.route",
}

_TYPE_CHECKS: dict[str, type | tuple[type, ...]] = {
    "integer": int,
    "number": (int, float),
    "string": str,
    "boolean": bool,
}


def schema_for(name: str) -> dict[str, Any] | None:
    return next(
        (schema for schema in TOOL_SCHEMAS if schema["function"]["name"] == name),
        None,
    )


def validate_tool_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Check model-supplied arguments against the tool schema; return them unchanged.

    The model is untrusted input: a missing date or an invented absence type must
    fail here with a readable message, never reach the services layer half-filled.
    """
    schema = schema_for(name)
    if schema is None:
        raise ValidationError(f"Неизвестный инструмент: {name}")
    parameters = schema["function"]["parameters"]
    properties: dict[str, Any] = parameters.get("properties", {})
    missing = [key for key in parameters.get("required", []) if args.get(key) in (None, "")]
    if missing:
        raise ValidationError(f"{', '.join(missing)}: обязательное поле не заполнено")
    unknown = [key for key in args if key not in properties]
    if unknown:
        raise ValidationError(f"{', '.join(unknown)}: неизвестный параметр")

    for key, value in args.items():
        if value is None:
            continue
        spec = properties[key]
        kind = spec.get("type", "")
        expected = _TYPE_CHECKS.get(kind)
        if expected is not None:
            # bool is an int in Python; a JSON `true` is not a valid request_id.
            numeric = kind in {"integer", "number"}
            if not isinstance(value, expected) or (numeric and isinstance(value, bool)):
                raise ValidationError(f"{key}: ожидается {kind}")
        choices = spec.get("enum")
        if choices and value not in choices:
            raise ValidationError(f"{key}: допустимо {', '.join(choices)}")
        if spec.get("format") == "date" and isinstance(value, str):
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValidationError(f"{key}: ожидается дата YYYY-MM-DD") from exc
    return args
