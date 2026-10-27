# FastAPIOrders

Build the order intake endpoint of a shop with FastAPI. Keep the data in memory. Clients retry on timeouts, so creating an order must be safe to repeat.

Write a function `solution()` that returns a new `fastapi.FastAPI` application. Each call returns an independent app with its own empty store.

`POST /orders` takes a JSON body:

```
{"currency": "EUR" | "USD" | "GBP", "items": [{"sku": <string>, "quantity": <int>, "unit_price": <int, cents>}], "coupon": <string, optional>}
```

- `items` has 1 to 50 entries. A `sku` is 3 to 20 characters from `A-Z`, `0-9` and `-`. `quantity` is 1 to 100. `unit_price` is 1 or more. The same `sku` may not appear twice.
- The only valid coupon is `SAVE10`, which takes 10 percent off the subtotal, rounded down to whole cents. Any other coupon responds `422`.
- It responds `201` with `{"id": <int>, "currency": <string>, "subtotal": <int>, "discount": <int>, "total": <int>}`. IDs start at 1 and increase by 1.

The request must carry an `Idempotency-Key` header of 1 to 64 characters. Without one it responds `400` with `{"detail": "Idempotency-Key header required"}`. A repeat of a request with the same key and the same body, compared after validation so that a missing `coupon` equals `"coupon": null`, responds `200` with the order from the first request and creates nothing. The same key with a different body responds `409` with `{"detail": "Idempotency-Key reused with a different body"}`.

`GET /orders/{id}` responds `200` with the order, or `404` with `{"detail": "Order not found"}`.

Any other invalid body responds `422`.

The tests use `fastapi.testclient.TestClient`. `fastapi` and `httpx` are installed.

```python
from fastapi.testclient import TestClient

client = TestClient(solution())
body = {"currency": "EUR", "items": [{"sku": "PEN-01", "quantity": 3, "unit_price": 199}, {"sku": "PAD", "quantity": 1, "unit_price": 350}], "coupon": "SAVE10"}

first = client.post("/orders", json=body, headers={"Idempotency-Key": "k1"})
assert first.status_code == 201
assert first.json() == {"id": 1, "currency": "EUR", "subtotal": 947, "discount": 94, "total": 853}

again = client.post("/orders", json=body, headers={"Idempotency-Key": "k1"})
assert again.status_code == 200 and again.json() == first.json()

changed = client.post("/orders", json={**body, "coupon": None}, headers={"Idempotency-Key": "k1"})
assert changed.status_code == 409

second = client.post("/orders", json={"currency": "GBP", "items": [{"sku": "INK", "quantity": 2, "unit_price": 500}]}, headers={"Idempotency-Key": "k2"})
assert second.json() == {"id": 2, "currency": "GBP", "subtotal": 1000, "discount": 0, "total": 1000}

assert client.post("/orders", json=body).status_code == 400
assert client.post("/orders", json={**body, "coupon": "FREE"}, headers={"Idempotency-Key": "k3"}).status_code == 422
assert client.post("/orders", json={**body, "items": []}, headers={"Idempotency-Key": "k4"}).status_code == 422
duplicate = {"currency": "EUR", "items": [{"sku": "PAD", "quantity": 1, "unit_price": 1}, {"sku": "PAD", "quantity": 2, "unit_price": 1}]}
assert client.post("/orders", json=duplicate, headers={"Idempotency-Key": "k5"}).status_code == 422

assert client.get("/orders/2").json()["total"] == 1000
assert client.get("/orders/9").status_code == 404
```
