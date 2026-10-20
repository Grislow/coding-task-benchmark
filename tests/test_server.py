import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from test_benchmark import ScriptedAgent, SleepySolver, _CORRECT, _TASK, _WRONG

from ctb.server import bind
from ctb.session import RunSession


def _open(session: RunSession, page: str = "<p>ctb</p>"):
    server = bind(session, page, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _url(server: object, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _request(url: str, body: str | None = None) -> tuple[int, bytes]:
    data = None if body is None else body.encode()
    request = urllib.request.Request(url, data=data, method="GET" if data is None else "POST")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _wait_done(server: object) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, raw = _request(_url(server, "/status"))
        assert status == 200
        snapshot = json.loads(raw)
        if snapshot["phase"] in {"done", "error"}:
            return snapshot
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def test_the_server_listens_on_localhost_and_serves_one_run(tmp_path: Path) -> None:
    session = RunSession(
        [ScriptedAgent("fast", [_CORRECT], tokens=10), ScriptedAgent("slow", [_WRONG, _CORRECT], tokens=10)],
        ScriptedAgent("author", [], tokens=1),
        attempts=2,
        timeout_s=30,
        review=True,
        out_root=tmp_path,
    )
    server = _open(session)
    try:
        host, _port = server.server_address
        assert host == "127.0.0.1"
        status, page = _request(_url(server, "/"))
        assert status == 200
        assert b"ctb" in page
        status, missing = _request(_url(server, "/missing"))
        assert status == 404
        assert missing == b"Not found"
        status, started = _request(_url(server, "/task"), _TASK)
        assert status == 200
        snapshot = _wait_done(server)
        assert snapshot["phase"] == "done"
        status, source = _request(_url(server, "/solution?agent=slow&attempt=2"))
        assert status == 200
        assert b"while N" in source
        status, kept = _request(_url(server, "/solution?agent=slow"))
        assert status == 200
        assert b"while N" in kept
        status, mine = _request(_url(server, "/mine"), _CORRECT)
        assert status == 200
        deadline = time.monotonic() + 30
        you = None
        while time.monotonic() < deadline:
            status, raw = _request(_url(server, "/status"))
            body = json.loads(raw)
            you = body["candidate"]
            if isinstance(you, dict) and you.get("profile") is not None and len(you["reviews"]) == 2:
                break
            time.sleep(0.02)
        assert isinstance(you, dict)
        assert you["passed"] is True
        assert {item["reviewer"] for item in you["reviews"]} == {"fast", "slow"}
        status, yours = _request(_url(server, "/solution?agent=you"))
        assert status == 200
        assert b"def solution" in yours
    finally:
        server.shutdown()


def test_a_second_task_is_rejected_while_the_run_is_active(tmp_path: Path) -> None:
    session = RunSession(
        [SleepySolver("first")],
        ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=False,
        out_root=tmp_path,
    )
    server = _open(session)
    try:
        assert _request(_url(server, "/task"), _TASK)[0] == 200
        status, body = _request(_url(server, "/task"), _TASK)
        assert status == 409
        assert b"already active" in body
        assert _wait_done(server)["phase"] == "done"
    finally:
        server.shutdown()
