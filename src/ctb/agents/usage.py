import json

from ctb.models import AgentResult, TokenUsage


def parse_json_object(text: str) -> dict[str, object]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty CLI output")
    payload = _load_object(stripped)
    if payload is None:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("CLI output was not a JSON object")
        payload = _load_object(stripped[start : end + 1])
    if payload is None:
        raise ValueError("CLI output was not a JSON object")
    return payload


def result_from_stdout(stdout: str, stderr: str, returncode: int, wall_ms: int) -> AgentResult:
    try:
        payload = parse_json_object(stdout)
    except ValueError:
        message = stderr.strip() or stdout.strip() or f"CLI exited {returncode}"
        return AgentResult(
            ok=False,
            text="",
            session_id=None,
            usage=TokenUsage(),
            wall_ms=wall_ms,
            cost_usd=None,
            error=message[:4000],
            raw={},
        )
    text = _first_string(payload, ("text", "result")) or ""
    session_id = _first_string(payload, ("sessionId", "session_id"))
    usage_payload = payload.get("usage")
    usage = usage_from(usage_payload if isinstance(usage_payload, dict) else None)
    is_error = payload.get("is_error") is True or payload.get("type") == "error" or returncode != 0
    error = None
    if is_error:
        error = _first_string(payload, ("message",)) or stderr.strip() or f"CLI exited {returncode}"
        error = error[:4000]
    return AgentResult(
        ok=not is_error,
        text=text,
        session_id=session_id,
        usage=usage,
        wall_ms=wall_ms,
        cost_usd=_optional_float(payload, "total_cost_usd"),
        error=error,
        raw=payload,
    )


def result_from_gemini_json(stdout: str, stderr: str, returncode: int, wall_ms: int) -> AgentResult:
    payload = {}
    for text in (stdout, stderr):
        try:
            payload = parse_json_object(text)
            break
        except ValueError:
            continue
    failure = payload.get("error")
    error = None
    if isinstance(failure, dict) or returncode != 0 or not payload:
        message = _first_string(failure, ("message",)) if isinstance(failure, dict) else None
        error = (message or stderr.strip() or stdout.strip() or f"CLI exited {returncode}")[:4000]
    stats = payload.get("stats")
    models = stats.get("models") if isinstance(stats, dict) else None
    usage = TokenUsage()
    for entry in models.values() if isinstance(models, dict) else []:
        tokens = entry.get("tokens") if isinstance(entry, dict) else None
        if isinstance(tokens, dict):
            cached = _int_field(tokens, "cached")
            usage = TokenUsage(
                input_tokens=usage.input_tokens + _int_field(tokens, "prompt") - cached,
                output_tokens=usage.output_tokens + _int_field(tokens, "candidates"),
                cache_read_tokens=usage.cache_read_tokens + cached,
                reasoning_tokens=usage.reasoning_tokens + _int_field(tokens, "thoughts"),
            )
    return AgentResult(
        ok=error is None,
        text=_first_string(payload, ("response",)) or "",
        session_id=_first_string(payload, ("session_id", "sessionId")),
        usage=usage,
        wall_ms=wall_ms,
        cost_usd=None,
        error=error,
        raw=payload,
    )


def result_from_codex_jsonl(stdout: str, stderr: str, returncode: int, wall_ms: int) -> AgentResult:
    events = _jsonl_objects(stdout)
    if not events:
        return result_from_stdout(stdout, stderr, returncode, wall_ms)
    thread_id: str | None = None
    usage = TokenUsage()
    messages: list[str] = []
    failures: list[str] = []
    for payload in events:
        kind = payload.get("type")
        if kind == "thread.started":
            thread_id = _string_field(payload, "thread_id") or thread_id
        elif kind == "turn.completed":
            turn_usage = payload.get("usage")
            if isinstance(turn_usage, dict):
                usage = usage.add(_codex_usage(turn_usage))
        elif kind == "turn.failed":
            message = _nested_message(payload.get("error"))
            if message:
                failures.append(message)
        elif kind == "error":
            message = _string_field(payload, "message")
            if message and not message.startswith("Reconnecting"):
                failures.append(message)
        elif kind == "item.completed":
            text = _agent_message(payload.get("item"))
            if text:
                messages.append(text)
    ok = returncode == 0 and not failures
    error = None
    if not ok:
        error = failures[-1] if failures else stderr.strip() or f"codex exited {returncode}"
        error = error[:4000]
    return AgentResult(
        ok=ok,
        text=messages[-1] if messages else "",
        session_id=thread_id,
        usage=usage,
        wall_ms=wall_ms,
        cost_usd=None,
        error=error,
        raw={},
    )


def usage_from(payload: dict[str, object] | None) -> TokenUsage:
    if payload is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=_int_field(payload, "input_tokens"),
        output_tokens=_int_field(payload, "output_tokens"),
        cache_read_tokens=_int_field(payload, "cache_read_input_tokens"),
        cache_creation_tokens=_int_field(payload, "cache_creation_input_tokens"),
        reasoning_tokens=_int_field(payload, "reasoning_tokens"),
    )


def _load_object(text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return _string_keyed(payload)
    return None


def _string_keyed(payload: dict[object, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(key, str):
            result[key] = value
    return result


def _first_string(payload: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _int_field(payload: dict[str, object], key: str) -> int:
    value = payload.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def _codex_usage(payload: dict[str, object]) -> TokenUsage:
    # Codex counts cached input inside input_tokens. The published sample has
    # input_tokens 24763 and cached_input_tokens 24448, so cache is a subset.
    raw_input = _int_field(payload, "input_tokens")
    cached = _int_field(payload, "cached_input_tokens")
    if cached > raw_input:
        cached = 0
    return TokenUsage(
        input_tokens=raw_input - cached,
        output_tokens=_int_field(payload, "output_tokens"),
        cache_read_tokens=cached,
    )


def _jsonl_objects(stdout: str) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    for line in stdout.splitlines():
        payload = _load_object(line.strip())
        if payload is not None:
            objects.append(payload)
    return objects


def _agent_message(item: object) -> str | None:
    if not isinstance(item, dict) or item.get("type") != "agent_message":
        return None
    text = item.get("text")
    if isinstance(text, str) and text:
        return text
    return None


def _nested_message(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    return _string_field(_string_keyed(payload), "message")


def _string_field(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _optional_float(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
