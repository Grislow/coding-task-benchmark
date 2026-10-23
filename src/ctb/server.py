import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ctb.prompts import TECHS
from ctb.session import RunSession


class LoopbackServer(ThreadingHTTPServer):
    def __init__(self, session: RunSession, page: str, port: int) -> None:
        self.session = session
        self.page = page
        super().__init__(("127.0.0.1", port), Handler)


def bind(session: RunSession, page: str, port: int = 0) -> LoopbackServer:
    return LoopbackServer(session, page, port)


class Handler(BaseHTTPRequestHandler):
    server: LoopbackServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/status":
            self._json(200, self.server.session.snapshot())
            return
        if parsed.path == "/solution":
            source = _solution(self.server.session.snapshot(), parse_qs(parsed.query))
            if source is None:
                self._text(404, "Not found")
                return
            self._text(200, source)
            return
        if parsed.path == "/":
            self._bytes(200, "text/html; charset=utf-8", self.server.page.encode())
            return
        self._text(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self._body()
        if parsed.path == "/task":
            if not body.strip():
                self._text(400, "The task description is empty.")
                return
            tech = parse_qs(parsed.query).get("tech", [None])[0]
            if tech is not None and tech not in TECHS:
                self._text(400, f"Unknown tech. Use one of: {', '.join(TECHS)}.")
                return
            try:
                snapshot = self.server.session.start(body, tech)
            except RuntimeError as exc:
                self._text(409, str(exc))
                return
            self._json(200, snapshot)
            return
        if parsed.path == "/reset":
            try:
                snapshot = self.server.session.reset()
            except RuntimeError as exc:
                self._text(409, str(exc))
                return
            self._json(200, snapshot)
            return
        if parsed.path == "/mine":
            try:
                snapshot = self.server.session.submit_mine(body)
            except RuntimeError as exc:
                status = 409 if "already" in str(exc) else 400
                self._text(status, str(exc))
                return
            self._json(200, snapshot)
            return
        self._text(404, "Not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _body(self) -> str:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode()

    def _json(self, status: int, payload: dict[str, object]) -> None:
        self._bytes(status, "application/json", json.dumps(payload).encode())

    def _text(self, status: int, text: str) -> None:
        self._bytes(status, "text/plain; charset=utf-8", text.encode())

    def _bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _solution(snapshot: dict[str, object], query: dict[str, list[str]]) -> str | None:
    names = query.get("agent")
    if not names or not names[0]:
        return None
    agent = names[0]
    if agent == "you":
        candidate = snapshot.get("candidate")
        if not isinstance(candidate, dict):
            return None
        source = candidate.get("source")
        return source if isinstance(source, str) and source else None
    attempt_raw = query.get("attempt")
    if attempt_raw:
        try:
            number = int(attempt_raw[0])
        except ValueError:
            return None
        return _attempt_source(snapshot, agent, number)
    solutions = snapshot.get("solutions")
    if isinstance(solutions, list):
        for item in solutions:
            if isinstance(item, dict) and item.get("agent") == agent:
                source = item.get("source")
                if isinstance(source, str) and source:
                    return source
    attempts = snapshot.get("attempts")
    if isinstance(attempts, list):
        for item in attempts:
            if (
                isinstance(item, dict)
                and item.get("agent") == agent
                and item.get("chosen") is True
            ):
                source = item.get("source")
                if isinstance(source, str) and source:
                    return source
    return None


def _attempt_source(snapshot: dict[str, object], agent: str, number: int) -> str | None:
    attempts = snapshot.get("attempts")
    if not isinstance(attempts, list):
        return None
    for item in attempts:
        if isinstance(item, dict) and item.get("agent") == agent and item.get("number") == number:
            source = item.get("source")
            return source if isinstance(source, str) and source else None
    return None
