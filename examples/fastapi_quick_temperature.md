# QuickTemperature

Build a one-endpoint FastAPI service that converts temperatures.

Write a function `solution()` that returns a `fastapi.FastAPI` application with `GET /convert`. It takes the query parameters `value` (a number) and `unit` (`C` or `F`), and responds `200` with `{"celsius": <number>, "fahrenheit": <number>}`, both rounded to 1 decimal place. A value below absolute zero (-273.15 C, or -459.67 F) or any other invalid parameter responds `422`.

The tests use `fastapi.testclient.TestClient`. `fastapi` and `httpx` are installed.

```python
from fastapi.testclient import TestClient

client = TestClient(solution())
assert client.get("/convert", params={"value": 100, "unit": "C"}).json() == {"celsius": 100.0, "fahrenheit": 212.0}
assert client.get("/convert", params={"value": -40, "unit": "F"}).json() == {"celsius": -40.0, "fahrenheit": -40.0}
assert client.get("/convert", params={"value": 98.6, "unit": "F"}).json() == {"celsius": 37.0, "fahrenheit": 98.6}
assert client.get("/convert", params={"value": -300, "unit": "C"}).status_code == 422
assert client.get("/convert", params={"value": 10, "unit": "K"}).status_code == 422
assert client.get("/convert").status_code == 422
```
