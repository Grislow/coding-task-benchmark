# FastAPIUrlShortener

Build a small link shortener with FastAPI. Keep the data in memory.

Write a function `solution()` that returns a new `fastapi.FastAPI` application. Each call returns an independent app with its own empty store.

The app has these endpoints:

- `POST /links` takes a JSON body `{"url": <string>, "alias": <string, optional>}`. The `url` must be an absolute `http` or `https` URL with a host. The `alias`, when given, is 3 to 30 characters from `a-z`, `A-Z`, `0-9`, `_` and `-`. It responds `201` with `{"code": <string>, "url": <string>}`. With an alias, the code is the alias. Without one, the code is 7 characters from `a-z`, `A-Z` and `0-9` that no other link uses. Shortening the same URL twice without an alias gives two different codes.
- `GET /{code}` responds `307` with a `Location` header set to the link's URL and counts one hit.
- `GET /links/{code}` responds `200` with `{"code": <string>, "url": <string>, "hits": <int>}`. It does not count a hit.
- `DELETE /links/{code}` responds `204` with an empty body. The code can then be used again as an alias.

An alias that is already taken responds `409` with `{"detail": "Alias already in use"}`. A code that does not exist responds `404` with `{"detail": "Link not found"}`. An invalid body responds `422`.

The tests use `fastapi.testclient.TestClient`. `fastapi` and `httpx` are installed.

```python
from fastapi.testclient import TestClient

client = TestClient(solution(), follow_redirects=False)

made = client.post("/links", json={"url": "https://example.com/docs?page=2"})
assert made.status_code == 201
code = made.json()["code"]
assert len(code) == 7 and code.isalnum()
assert client.post("/links", json={"url": "https://example.com/docs?page=2"}).json()["code"] != code

jump = client.get("/" + code)
assert jump.status_code == 307
assert jump.headers["location"] == "https://example.com/docs?page=2"
assert client.get("/links/" + code).json() == {"code": code, "url": "https://example.com/docs?page=2", "hits": 1}

assert client.post("/links", json={"url": "http://intra.net", "alias": "team-wiki"}).json() == {"code": "team-wiki", "url": "http://intra.net"}
taken = client.post("/links", json={"url": "http://other.net", "alias": "team-wiki"})
assert taken.status_code == 409 and taken.json() == {"detail": "Alias already in use"}

assert client.post("/links", json={"url": "ftp://files.net"}).status_code == 422
assert client.post("/links", json={"url": "https://ok.net", "alias": "a b"}).status_code == 422

assert client.delete("/links/team-wiki").status_code == 204
assert client.get("/team-wiki").status_code == 404
assert client.get("/links/team-wiki").json() == {"detail": "Link not found"}
```
