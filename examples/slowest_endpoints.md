# SlowestEndpoints

A web service writes one access-log line per request in this format:

```
<METHOD> <PATH> <STATUS> <DURATION_MS>
```

For example `GET /users/42 200 31`. Lines are separated by single spaces as shown, with no leading or trailing spaces.

Requests are grouped into endpoints by method and path. Any path segment that consists only of digits is a resource id and is replaced with `{id}`, so `GET /users/42` and `GET /users/7` are the same endpoint, `GET /users/{id}`. The query string, if any (everything from `?` on), is ignored.

Only successful requests count: those with a status from 200 to 399 inclusive. The latency of an endpoint is the median duration of its successful requests. For an even number of requests, it is the mean of the two middle values.

Write a function `solution(logs, k)` that returns the `k` slowest endpoints as a list of strings `"<METHOD> <PATH>"`. Order them by latency, highest first. Break ties by the endpoint string in ascending lexicographic order. If fewer than `k` endpoints have at least one successful request, return all of them.

Assume that:

- `logs` has between 0 and 100,000 elements, each in the format above;
- `METHOD` is one of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`;
- `PATH` starts with `/` and has at most 200 characters;
- `STATUS` is an integer within the range [100..599];
- `DURATION_MS` is an integer within the range [0..1,000,000];
- `k` is an integer within the range [1..1,000].

```python
logs = [
    "GET /users/1 200 30",
    "GET /users/2 200 50",
    "GET /users/3 500 900",
    "POST /users 201 120",
    "GET /health 200 1",
    "GET /orders/7/items?page=2 200 80",
    "GET /orders/8/items 200 60",
]
assert solution(logs, 2) == ["POST /users", "GET /orders/{id}/items"]
assert solution(logs, 10) == ["POST /users", "GET /orders/{id}/items", "GET /users/{id}", "GET /health"]
assert solution([], 3) == []
assert solution(["GET /a 404 10", "GET /b 302 10", "GET /c 200 10"], 5) == ["GET /b", "GET /c"]
```
