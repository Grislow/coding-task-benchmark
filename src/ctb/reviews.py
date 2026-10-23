import json

from ctb.models import Finding, ReviewNote
from ctb.score import findings_score

_SEVERITIES = ("blocker", "major", "minor")


def parse_review(text: str, reviewer: str, rules: frozenset[str], line_count: int) -> ReviewNote | None:
    rubric = _find_rubric(_decode(text))
    if rubric is None:
        return None
    findings = _findings(rubric.get("findings"), rules, line_count)
    return ReviewNote(
        reviewer=reviewer,
        score=findings_score(findings),
        findings=findings,
        summary=_text(rubric.get("summary")),
    )


def _findings(value: object, rules: frozenset[str], line_count: int) -> tuple[Finding, ...]:
    if not isinstance(value, list):
        return ()
    kept: dict[tuple[int, str], Finding] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        line = item.get("line")
        rule = _text(item.get("rule")).upper()
        severity = _text(item.get("severity")).lower()
        if isinstance(line, bool) or not isinstance(line, int) or not 1 <= line <= line_count:
            continue
        if rule not in rules or severity not in _SEVERITIES:
            continue
        kept.setdefault(
            (line, rule),
            Finding(line, rule, severity, _text(item.get("issue")), _text(item.get("fix"))),
        )
    return tuple(sorted(kept.values(), key=lambda finding: finding.line))


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
        if "findings" in keyed:
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


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
