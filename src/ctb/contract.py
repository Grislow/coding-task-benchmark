import json
import subprocess
import sys
import tempfile
from pathlib import Path

_PROBE = """
import json
import typing

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from solution import solution

try:
    from perf_cases import CASES
except Exception:
    CASES = []

args, kwargs = CASES[0] if CASES else ((), {})
app = solution(*args, **kwargs)
client = TestClient(app, raise_server_exceptions=False)
checks = []


def numeric(param):
    annotation = param.field_info.annotation
    return any(option in (int, float) for option in (typing.get_args(annotation) or (annotation,)))


def fill(route, value):
    path = route.path_format
    for param in route.dependant.path_params:
        path = path.replace("{" + param.name + "}", value)
    return path


def survives(label, method, path, **request):
    status = client.request(method, path, **request).status_code
    checks.append([status < 500, f"{label} returned {status}"])


for route in app.routes:
    if not isinstance(route, APIRoute):
        continue
    for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
        name = f"{method} {route.path}"
        typed = route.response_model is not None or route.status_code == 204
        checks.append([typed, f"{name} has no response model"])
        path = fill(route, "1")
        if route.dependant.path_params:
            survives(f"{name} with a non-numeric id", method, fill(route, "not-a-number"))
        for param in route.dependant.query_params:
            if numeric(param):
                survives(f"{name} with {param.alias}=not-a-number", method, path, params={param.alias: "not-a-number"})
        if route.body_field is not None or method in {"POST", "PUT", "PATCH"}:
            survives(f"{name} with no body", method, path)
            survives(f"{name} with a list body", method, path, json=[1])
            survives(f"{name} with a string body", method, path, json="x")
        elif method == "GET" and not route.dependant.path_params:
            survives(f"{name} with defaults", method, path)

print(json.dumps(checks))
"""


def contract_report(source: str, perf_cases: str | None, timeout_s: int) -> tuple[float | None, str]:
    with tempfile.TemporaryDirectory(prefix="ctb-contract-") as directory:
        root = Path(directory)
        (root / "solution.py").write_text(source)
        if perf_cases:
            (root / "perf_cases.py").write_text(perf_cases)
        (root / "probe.py").write_text(_PROBE)
        try:
            completed = subprocess.run(
                [sys.executable, "probe.py"],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=min(timeout_s, 60),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 0.0, "The contract probe timed out."
    try:
        checks = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        reason = (completed.stderr.strip().splitlines() or ["no output"])[-1]
        return 0.0, f"The app could not be probed: {reason[:300]}"
    if not checks:
        return None, "The app has no routes to probe."
    failures = [label for ok, label in checks if not ok]
    score = 100.0 * (len(checks) - len(failures)) / len(checks)
    if not failures:
        return score, f"{len(checks)} contract checks passed."
    passed = len(checks) - len(failures)
    return score, f"{passed}/{len(checks)} contract checks passed. " + "; ".join(failures[:5]) + "."
