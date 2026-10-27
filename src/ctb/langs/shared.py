import json
import subprocess
import xml.etree.ElementTree as element_tree
from pathlib import Path


def read_junit(path: Path, stdout: str, stderr: str) -> tuple[int, int, str]:
    if not path.exists():
        return 0, 0, stdout or stderr
    try:
        root = element_tree.parse(path).getroot()
    except element_tree.ParseError:
        return 0, 0, stdout or stderr
    cases = list(root.iter("testcase"))
    messages: list[str] = []
    for case in cases:
        for child in case:
            if child.tag in {"failure", "error"}:
                detail = (child.get("message") or child.text or "").strip()
                messages.append(f"{case.get('name', 'test')}: {detail}")
                break
    excerpt = "\n".join(messages[:8]) or stdout or stderr
    return len(cases) - len(messages), len(cases), excerpt


def run(
    command: list[str],
    cwd: Path,
    timeout_s: int,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def score_checks(stdout: str, stderr: str) -> tuple[float | None, str]:
    try:
        checks = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        reason = (stderr.strip().splitlines() or ["no output"])[-1]
        return 0.0, f"The app could not be probed: {reason[:300]}"
    if not checks:
        return None, "The app has no routes to probe."
    failures = [label for ok, label in checks if not ok]
    score = 100.0 * (len(checks) - len(failures)) / len(checks)
    if not failures:
        return score, f"{len(checks)} contract checks passed."
    passed = len(checks) - len(failures)
    return score, f"{passed}/{len(checks)} contract checks passed. " + "; ".join(failures[:5]) + "."
