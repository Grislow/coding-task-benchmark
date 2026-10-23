import pytest

from ctb.checks import readability_report
from ctb.contract import contract_report

_TIDY = '''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class Todo(BaseModel):
    id: int
    title: str


class NewTodo(BaseModel):
    title: str


def solution():
    app = FastAPI()
    todos: dict[int, Todo] = {}

    @app.post("/todos", status_code=201, response_model=Todo)
    def create(body: NewTodo):
        todo = Todo(id=len(todos) + 1, title=body.title)
        todos[todo.id] = todo
        return todo

    @app.get("/todos/{todo_id}", response_model=Todo)
    def read(todo_id: int):
        if todo_id not in todos:
            raise HTTPException(404, "Todo not found")
        return todos[todo_id]

    return app
'''

_SLOPPY = '''from fastapi import FastAPI, Request


def solution():
    app = FastAPI()
    todos = {}

    @app.post("/todos")
    async def create(request: Request):
        body = await request.json()
        todos[len(todos) + 1] = body["title"]
        return {"id": len(todos)}

    @app.get("/todos/{todo_id}")
    def read(todo_id):
        return {"title": todos[int(todo_id)]}

    return app
'''


def test_contract_rewards_typed_routes_that_reject_bad_input() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    tidy, tidy_note = contract_report(_TIDY, None, 60)
    sloppy, sloppy_note = contract_report(_SLOPPY, None, 60)
    assert tidy == 100
    assert "contract checks passed" in tidy_note
    assert sloppy == 0
    assert "returned 500" in sloppy_note
    assert "has no response model" in sloppy_note


def test_contract_reports_an_app_it_cannot_build() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    score, note = contract_report("def solution():\n    return 1\n", None, 60)
    assert score == 0
    assert "could not be probed" in note


def test_static_check_uses_the_rule_set_for_the_tech() -> None:
    clean = "def solution(A):\n    return max(A, default=0)\n"
    messy = (
        "def solution(A, seen=[]):\n"
        "    out = []\n"
        "    for i in range(len(A)):\n"
        "        if A[i] == True:\n"
        "            out.append(A[i])\n"
        "    return out\n"
    )
    score, note = readability_report(clean)
    assert score == 100
    assert "ruff clean" in note
    score, note = readability_report(messy)
    assert score < 100
    assert "B006" in note and "E712" in note
    fastapi_only = (
        "from fastapi import Depends, FastAPI\n\n"
        "app = FastAPI()\n\n\n"
        "def store():\n"
        "    return {}\n\n\n"
        '@app.get("/items")\n'
        "def read(items: dict = Depends(store)):\n"
        "    return items\n"
    )
    assert "FAST002" not in readability_report(fastapi_only, "python")[1]
    assert "FAST002" in readability_report(fastapi_only, "fastapi")[1]
