# QuickCounter

Build a tiny counter API with Express. Keep the count in memory.

Write a function `solution()` that returns a new Express application, and export it with `module.exports = { solution };`. Each call returns an independent app whose count starts at 0.

- `GET /count` responds `200` with `{"count": <int>}`.
- `POST /count` takes `{"by": <int from 1 to 100>}`, adds it to the count and responds `200` with `{"count": <int>}`. An invalid body responds `422` with `{"detail": <message>}`.

The tests start the app with `app.listen(0)` and call it with the built-in `fetch`. `express` is installed.

```js
const server = solution().listen(0);
await new Promise((resolve) => server.once("listening", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const add = (body) => fetch(base + "/count", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

try {
  assert.deepEqual(await (await fetch(base + "/count")).json(), { count: 0 });
  assert.deepEqual(await (await add({ by: 5 })).json(), { count: 5 });
  assert.equal((await add({ by: 0 })).status, 422);
  assert.equal((await add({ by: "2" })).status, 422);
  assert.deepEqual(await (await fetch(base + "/count")).json(), { count: 5 });
} finally {
  server.close();
}
```
