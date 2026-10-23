# FastAPIPagination

Build a read-only product listing endpoint with FastAPI.

Write a function `solution(products)` that returns a `fastapi.FastAPI` application serving the given products. `products` is a list of dicts `{"id": <int>, "name": <string>, "price": <int>}`. IDs are unique. The app must not change the list it was given.

The app has one endpoint, `GET /products`, with these optional query parameters:

- `min_price` and `max_price` (integers, inclusive) filter by price.
- `q` (string) keeps products whose `name` contains `q`, ignoring case.
- `sort` is one of `id`, `price`, `-price` (price descending), or `name`. The default is `id`. Ties on price or name are broken by ascending `id`.
- `limit` is an integer from 1 to 50 and defaults to 10.
- `offset` is an integer of 0 or more and defaults to 0.

Filters are applied first, then sorting, then `offset` and `limit`. The response is `200` with:

```json
{"total": <int>, "items": [<product>, ...], "next_offset": <int or null>}
```

`total` is the number of products after filtering and before paging. `next_offset` is `offset + limit` if more filtered products remain after this page, otherwise `null`.

An out-of-range `limit` or `offset`, an unknown `sort` value, or `min_price` greater than `max_price` responds `422`.

The tests use `fastapi.testclient.TestClient`. `fastapi` and `httpx` are installed.

```python
from fastapi.testclient import TestClient

products = [
    {"id": 1, "name": "Keyboard", "price": 120},
    {"id": 2, "name": "Mouse", "price": 40},
    {"id": 3, "name": "Monitor", "price": 300},
    {"id": 4, "name": "Mouse pad", "price": 40},
    {"id": 5, "name": "USB hub", "price": 25},
]
client = TestClient(solution(products))

page = client.get("/products", params={"limit": 2}).json()
assert page == {"total": 5, "items": products[:2], "next_offset": 2}

last = client.get("/products", params={"limit": 2, "offset": 4}).json()
assert last["items"] == [products[4]] and last["next_offset"] is None

by_price = client.get("/products", params={"sort": "price"}).json()["items"]
assert [item["id"] for item in by_price] == [5, 2, 4, 1, 3]

mice = client.get("/products", params={"q": "MOUSE", "sort": "-price"}).json()
assert mice["total"] == 2 and [item["id"] for item in mice["items"]] == [2, 4]

cheap = client.get("/products", params={"min_price": 30, "max_price": 120}).json()
assert [item["id"] for item in cheap["items"]] == [1, 2, 4]

assert client.get("/products", params={"limit": 0}).status_code == 422
assert client.get("/products", params={"sort": "rating"}).status_code == 422
assert client.get("/products", params={"min_price": 50, "max_price": 10}).status_code == 422
assert products[0] == {"id": 1, "name": "Keyboard", "price": 120}
```
