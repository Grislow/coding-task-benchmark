# FastAPITodo

Build a small to-do API with FastAPI. Keep the data in memory. Do not use a database.

Write a function `solution()` that returns a new `fastapi.FastAPI` application. Each call returns an independent app with its own empty store.

The app has these endpoints:

- `POST /todos` takes a JSON body `{"title": <string>, "done": <bool, optional, default false>}`. The `title` has leading and trailing whitespace removed. It must then be 1 to 100 characters long. The endpoint creates the to-do and responds `201` with `{"id": <int>, "title": <string>, "done": <bool>}`. IDs start at 1 and increase by 1. An ID is never reused, even after a delete.
- `GET /todos` responds `200` with the list of to-dos in ascending `id` order. The optional query parameter `done` (`true` or `false`) keeps only to-dos with that value.
- `GET /todos/{id}` responds `200` with the to-do.
- `PATCH /todos/{id}` takes a JSON body with any of `title` and `done`, validated as above, updates only the fields that are given, and responds `200` with the updated to-do.
- `DELETE /todos/{id}` responds `204` with an empty body.

A request for an `id` that does not exist responds `404` with `{"detail": "Todo not found"}`. An invalid body or query parameter responds `422`.

The tests use `fastapi.testclient.TestClient`. `fastapi` and `httpx` are installed.

```python
from fastapi.testclient import TestClient

client = TestClient(solution())
assert client.get("/todos").json() == []

created = client.post("/todos", json={"title": "  write tests  "})
assert created.status_code == 201
assert created.json() == {"id": 1, "title": "write tests", "done": False}

assert client.post("/todos", json={"title": "ship", "done": True}).json()["id"] == 2
assert client.post("/todos", json={"title": "   "}).status_code == 422
assert client.post("/todos", json={}).status_code == 422

assert [todo["id"] for todo in client.get("/todos", params={"done": "true"}).json()] == [2]

patched = client.patch("/todos/1", json={"done": True})
assert patched.status_code == 200
assert patched.json() == {"id": 1, "title": "write tests", "done": True}

assert client.delete("/todos/1").status_code == 204
missing = client.get("/todos/1")
assert missing.status_code == 404
assert missing.json() == {"detail": "Todo not found"}
assert client.post("/todos", json={"title": "next"}).json()["id"] == 3

assert TestClient(solution()).get("/todos").json() == []
```
