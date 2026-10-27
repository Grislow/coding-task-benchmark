import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ctb.agents.preflight import installed_clis
from ctb.cli import CONFIG, _build_agent
from ctb.langs import lang
from ctb.run.workspace import scratch_dir

ROOT = Path("practice")
ALIASES = {"js": "javascript", "node": "javascript"}
EXTRACT = """Read task.md. Do not solve the task.
Write examples.json in this folder: a JSON list with one object per example the task gives with its expected result.
Each object has "call", the arguments exactly as they would be written inside solution(...) in {language},
and "expected", the expected return value written as a {language} literal.
Copy the values from the task. If the task states no examples with results, write [].
"""
PY_RUNNER = """import sys
from solution import solution

def run(label, call, expected=None, check=False):
    try:
        got = call()
    except Exception as exc:
        print(("  ✗ " if check else "  ") + f"solution({label}) raised {type(exc).__name__}: {exc}")
        return
    if not check:
        print(f"  solution({label}) → {got!r}")
    elif got == expected:
        print(f"  ✓ solution({label}) → {got!r}")
    else:
        print(f"  ✗ solution({label}) → {got!r}, expected {expected!r}")

"""
JS_RUNNER = """const assert = require("node:assert");
const { inspect } = require("node:util");
const { solution } = require("./solution");

function run(label, call, expected, check) {
  let got;
  try {
    got = call();
  } catch (error) {
    console.log((check ? "  ✗ " : "  ") + `solution(${label}) threw ${error}`);
    return;
  }
  if (!check) return console.log(`  solution(${label}) → ${inspect(got)}`);
  try {
    assert.deepStrictEqual(got, expected);
    console.log(`  ✓ solution(${label}) → ${inspect(got)}`);
  } catch {
    console.log(`  ✗ solution(${label}) → ${inspect(got)}, expected ${inspect(expected)}`);
  }
}

"""


def main() -> None:
    tech = ALIASES.get(sys.argv[1], sys.argv[1]) if len(sys.argv) > 1 else "python"
    toolchain = lang(tech)
    task = ROOT / "task.md"
    solution = ROOT / toolchain.SOLUTION
    inputs = ROOT / "inputs.txt"
    seen = None
    while True:
        create(toolchain, task, solution, inputs)
        stamp = tuple(path.stat().st_mtime_ns for path in (task, solution, inputs))
        if stamp != seen:
            seen = stamp
            check(toolchain, task, solution, inputs)
        time.sleep(0.5)


def create(toolchain, task: Path, solution: Path, inputs: Path) -> None:
    ROOT.mkdir(exist_ok=True)
    if not task.exists():
        task.write_text("Paste the task here.\n")
    if not solution.exists():
        solution.write_text(toolchain.STUB)
    if not inputs.exists():
        inputs.write_text("")
    toolchain.prepare(ROOT)


def check(toolchain, task: Path, solution: Path, inputs: Path) -> None:
    print("\033c", end="")
    print(f"Watching {ROOT}/. Edit task.md, {solution.name} or inputs.txt. Ctrl+C stops.\n", flush=True)
    text = task.read_text()
    public = toolchain.extract_public_tests(text)
    if public is not None:
        (ROOT / toolchain.PUBLIC).write_text(public)
        python = toolchain.FENCE == "python"
        command = [sys.executable, "-W", "ignore", "-m", "pytest", "-q", "--tb=short", "--no-header", "-rN", "-p", "no:cacheprovider", "-p", "no:warnings"] if python else ["node", "--test"]
        subprocess.run([*command, toolchain.PUBLIC], cwd=ROOT, check=False)
        return
    examples = load_examples(toolchain, text)
    customs = [line.strip() for line in inputs.read_text().splitlines() if line.strip()]
    runner = ROOT / ("run.py" if toolchain.FENCE == "python" else "run.js")
    runner.write_text(build_runner(toolchain, examples, customs))
    command = [sys.executable, runner.name] if toolchain.FENCE == "python" else ["node", runner.name]
    try:
        subprocess.run(command, cwd=ROOT, check=False, timeout=30)
    except subprocess.TimeoutExpired:
        print("  Stopped after 30 seconds.")


def build_runner(toolchain, examples: list[dict[str, str]], customs: list[str]) -> str:
    python = toolchain.FENCE == "python"

    def say(text: str) -> str:
        return f"print({text!r})" if python else f"console.log({json.dumps(text)});"

    def call(args: str, expected: str | None) -> str:
        if python:
            tail = f", {expected}, True" if expected is not None else ""
            return f"run({args!r}, lambda: solution({args}){tail})"
        tail = f", {expected}, true" if expected is not None else ", undefined, false"
        return f"run({json.dumps(args)}, () => solution({args}){tail});"

    lines = [PY_RUNNER if python else JS_RUNNER, say("Example tests")]
    lines.extend(call(item["call"], item["expected"]) for item in examples)
    if not examples:
        lines.append(say("  none found in task.md"))
    lines.append(say("\nCustom tests (inputs.txt)"))
    lines.extend(call(args, None) for args in customs)
    if not customs:
        lines.append(say("  add one input per line, like: 1041"))
    return "\n".join(lines) + "\n"


def load_examples(toolchain, text: str) -> list[dict[str, str]]:
    cache = ROOT / "examples.json"
    digest = hashlib.sha256(f"{toolchain.FENCE}\n{text}".encode()).hexdigest()
    if cache.exists():
        saved = json.loads(cache.read_text())
        if saved.get("task") == digest:
            print(f"Examples read by {saved['model']}, saved in {cache}.\n", flush=True)
            return saved["examples"]
    if text.strip() == "Paste the task here.":
        return []
    for name in CONFIG.get("practice", CONFIG["test_authors"]):
        if name.split(":")[0] not in installed_clis():
            continue
        print(f"Reading the examples in task.md with {name}…", flush=True)
        examples = extract(toolchain, text, name)
        if examples is not None:
            cache.write_text(json.dumps({"task": digest, "model": name, "examples": examples}, indent=2) + "\n")
            print(f"Saved to {cache}.\n")
            return examples
    print("No model could read the examples. Custom tests still run.\n")
    return []


def extract(toolchain, text: str, name: str) -> list[dict[str, str]] | None:
    workspace = scratch_dir("practice-")
    try:
        (workspace / "task.md").write_text(text)
        agent = _build_agent(name, 180, 0.5)
        language = "Python" if toolchain.FENCE == "python" else "JavaScript"
        prompt = EXTRACT.format(language=language)
        result = agent.complete(cwd=str(workspace), prompt=prompt, session_id=None, role="solve")
        found = workspace / "examples.json"
        if not result.ok or not found.exists():
            print(f"  {name} failed: {(result.error or 'it wrote no examples.json')[:200]}")
            return None
        examples = json.loads(found.read_text())
        if not isinstance(examples, list) or not all(isinstance(item, dict) and {"call", "expected"} <= item.keys() for item in examples):
            print(f"  {name} wrote examples in the wrong shape.")
            return None
        return [{"call": str(item["call"]), "expected": str(item["expected"])} for item in examples]
    except (OSError, ValueError) as exc:
        print(f"  {name} failed: {exc}")
        return None
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
