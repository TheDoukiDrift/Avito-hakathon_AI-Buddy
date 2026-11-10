"""OpenAI-compatible tool schemas — the same operations the MCP server exposes.

Keeping them side by side makes the "agent only talks to tools" rule visible in
one file: if a tool is added to `mcp_server`, it shows up here too.
"""

from __future__ import annotations

from typing import Any

_USER_ID = {
    "type": "integer",
    "description": "ID пользователя, от имени которого выполняется действие",
}
_ROLE = {
    "type": "string",
    "enum": ["intern", "mentor", "manager", "hr_bp"],
    "description": "Роль пользователя — проверяется на стороне сервисов",
}


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
            "user_id": _USER_ID,
            "role": _ROLE,
            "type": {"type": "string", "enum": ["day_off", "vacation", "sick"]},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "reason": {"type": "string"},
        },
        ["user_id", "role", "type", "date_from", "date_to"],
    ),
    _tool(
        "absence_status",
        "Показать статус заявки на отсутствие.",
        {"user_id": _USER_ID, "role": _ROLE, "request_id": {"type": "integer"}},
        ["user_id", "role", "request_id"],
    ),
    _tool(
        "absence_list",
        "Список заявок на отсутствие: свои или подопечных/команды.",
        {"user_id": _USER_ID, "role": _ROLE},
        ["user_id", "role"],
    ),
    _tool(
        "checklist_get",
        "Чек-лист адаптации с прогрессом.",
        {"user_id": _USER_ID, "role": _ROLE, "target_user_id": {"type": "integer"}},
        ["user_id", "role"],
    ),
    _tool(
        "checklist_complete",
        "Отметить пункт чек-листа выполненным (или снять отметку).",
        {
            "user_id": _USER_ID,
            "role": _ROLE,
            "item_id": {"type": "integer"},
        },
        ["user_id", "role", "item_id"],
    ),
    _tool(
        "contacts_lookup",
        "Найти, к кому обратиться по вопросу (наставник, руководитель, HR BP).",
        {"user_id": _USER_ID, "role": _ROLE, "query": {"type": "string"}},
        ["user_id", "role"],
    ),
]

TOOL_NAMES: frozenset[str] = frozenset(schema["function"]["name"] for schema in TOOL_SCHEMAS)
