import json

from ctb.models import ReviewNote


def parse_review(text: str, reviewer: str) -> ReviewNote | None:
    rubric = _find_rubric(_decode(text))
    if rubric is None:
        return None
    summary = rubric.get("summary")
    return ReviewNote(
        reviewer=reviewer,
        correctness=_bounded(rubric.get("correctness")),
        readability=_bounded(rubric.get("readability")),
        extensibility=_bounded(rubric.get("extensibility")),
        summary=summary if isinstance(summary, str) else "",
    )


def _decode(text: str) -> object:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = [line for line in stripped.splitlines() if not line.startswith("```")]
        stripped = "\n".join(lines)
    loaded = _loads(stripped)
    if loaded is not None:
        return loaded
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return stripped
    loaded = _loads(stripped[start : end + 1])
    return loaded if loaded is not None else stripped


def _find_rubric(value: object) -> dict[str, object] | None:
    if isinstance(value, str):
        loaded = _loads(value)
        if loaded is None:
            return None
        return _find_rubric(loaded)
    if isinstance(value, dict):
        keyed = {key: item for key, item in value.items() if isinstance(key, str)}
        if "extensibility" in keyed and "correctness" in keyed and "readability" in keyed:
            return keyed
        for item in keyed.values():
            found = _find_rubric(item)
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            found = _find_rubric(item)
            if found is not None:
                return found
    return None


def _loads(text: str) -> object | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _bounded(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return max(0, min(100, int(value)))
