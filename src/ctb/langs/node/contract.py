import shutil
import tempfile
from pathlib import Path

from ctb.langs.node.grade import stage
from ctb.langs.shared import run, score_checks

_PROBE = """
const { solution } = require("./solution");

let cases = [];
try {
  cases = require("./perf_cases");
} catch {
  cases = [];
}
const app = solution(...(cases[0] || []));
const router = app.router || app._router;
const checks = [];
const server = app.listen(0, async () => {
  const base = `http://127.0.0.1:${server.address().port}`;
  const send = async (label, method, path, body) => {
    const init = { method };
    if (body !== undefined) {
      init.headers = { "content-type": "application/json" };
      init.body = body;
    }
    try {
      const response = await fetch(base + path, init);
      checks.push([response.status < 500, `${label} returned ${response.status}`]);
    } catch (error) {
      checks.push([false, `${label} failed: ${error.message}`]);
    }
  };
  for (const layer of (router && router.stack) || []) {
    if (!layer.route || typeof layer.route.path !== "string") continue;
    const path = layer.route.path;
    const fill = (value) => path.replace(/:\\w+/g, value);
    const params = /:\\w+/.test(path);
    for (const method of Object.keys(layer.route.methods).filter((name) => name !== "_all")) {
      const verb = method.toUpperCase();
      const name = `${verb} ${path}`;
      if (params) await send(`${name} with a non-numeric id`, verb, fill("not-a-number"));
      if (["POST", "PUT", "PATCH"].includes(verb)) {
        await send(`${name} with no body`, verb, fill("1"));
        await send(`${name} with a list body`, verb, fill("1"), "[1]");
        await send(`${name} with a string body`, verb, fill("1"), '"x"');
        await send(`${name} with broken JSON`, verb, fill("1"), "{");
      } else if (verb === "GET" && !params) {
        await send(`${name} with defaults`, verb, path);
      }
    }
  }
  console.log(JSON.stringify(checks));
  process.exit(0);
});
"""


def contract_report(source: str, perf_cases: str | None, timeout_s: int) -> tuple[float | None, str]:
    if shutil.which("node") is None:
        return None, "node is not installed."
    with tempfile.TemporaryDirectory(prefix="ctb-contract-") as directory:
        root = Path(directory)
        stage(root, source)
        if perf_cases:
            (root / "perf_cases.js").write_text(perf_cases)
        (root / "probe.js").write_text(_PROBE)
        completed = run(["node", "probe.js"], root, min(timeout_s, 60))
    if completed is None:
        return 0.0, "The contract probe timed out."
    return score_checks(completed.stdout, completed.stderr)
