# StructuringData

A shop exports its order lines as flat rows, one row per item in an order. The account team wants them grouped by customer.

Write a function `solution(rows)`. Each row is a dict:

```
{"order_id": <str>, "customer": <str>, "sku": <str>, "quantity": <int>, "unit_price": <int, cents>}
```

Return a list with one dict per customer:

```
{"customer": <str>, "total": <int, cents>, "orders": [{"order_id": <str>, "items": <int>, "total": <int, cents>}, ...]}
```

- An order's `items` is the sum of its quantities, and its `total` is the sum of `quantity * unit_price` over its rows.
- A customer's `total` is the sum of their order totals.
- Orders are sorted by `order_id`. Customers are sorted by `total`, highest first, and then by name.
- Rows with a `quantity` of 0 or less are refunds already handled elsewhere. Skip them. An order whose rows are all skipped does not appear, and a customer with no orders left does not appear.
- Do not change the rows you were given.

There are at most 100,000 rows.

```python
rows = [
    {"order_id": "A2", "customer": "ada", "sku": "pen", "quantity": 2, "unit_price": 150},
    {"order_id": "A1", "customer": "ada", "sku": "pad", "quantity": 1, "unit_price": 400},
    {"order_id": "B1", "customer": "bob", "sku": "ink", "quantity": 3, "unit_price": 300},
    {"order_id": "A2", "customer": "ada", "sku": "ink", "quantity": 1, "unit_price": 300},
    {"order_id": "C1", "customer": "cy", "sku": "pen", "quantity": 0, "unit_price": 150},
]
assert solution(rows) == [
    {"customer": "ada", "total": 1000, "orders": [
        {"order_id": "A1", "items": 1, "total": 400},
        {"order_id": "A2", "items": 3, "total": 600},
    ]},
    {"customer": "bob", "total": 900, "orders": [{"order_id": "B1", "items": 3, "total": 900}]},
]
assert solution([]) == []
```
