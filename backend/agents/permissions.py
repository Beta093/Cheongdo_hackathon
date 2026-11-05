from typing import Any


ALLOWED_TOOLS = frozenset({"search_knowledge", "propose_calendar_event", "get_farm_context", "get_weather"})


def permission_allowed(request: Any) -> bool:
    # Unknown SDK shapes fail closed. Never approve by tool name alone.
    return (getattr(request, "kind", None) == "custom-tool"
            and getattr(request, "tool_name", None) in ALLOWED_TOOLS)


def on_permission_request(request: Any, context: Any = None) -> Any:
    from copilot.session import PermissionDecisionApproveOnce, PermissionDecisionUserNotAvailable

    if permission_allowed(request):
        return PermissionDecisionApproveOnce()
    return PermissionDecisionUserNotAvailable()
