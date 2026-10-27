# ExpressTodo

Build a small to-do API with Express. Keep the data in memory. Do not use a database.

Write a function `solution()` that returns a new Express application. Each call returns an independent app with its own empty store. Export it with `module.exports = { solution };`.

The app has these endpoints:

- `POST /todos` takes a JSON body `{"title": <string>, "done": <bool, optional, default false>}`. The `title` has leading and trailing whitespace removed. It must then be 1 to 100 characters long. The endpoint creates the to-do and responds `201` with `{"id": <int>, "title": <string>, "done": <bool>}`. IDs start at 1 and increase by 1. An ID is never reused, even after a delete.
- `GET /todos` responds `200` with the list of to-dos in ascending `id` order. The optional query parameter `done` (`true` or `false`) keeps only to-dos with that value.
- `GET /todos/:id` responds `200` with the to-do.
- `PATCH /todos/:id` takes a JSON body with any of `title` and `done`, validated as above, updates only the fields that are given, and responds `200` with the updated to-do.
- `DELETE /todos/:id` responds `204` with an empty body.

A request for an `id` that does not exist responds `404` with `{"detail": "Todo not found"}`. An invalid body or query parameter responds `422` with a `detail` message.

The tests start the app with `app.listen(0)` and call it with the built-in `fetch`. `express` is installed.

```js
const server = solution().listen(0);
await new Promise((resolve) => server.once("listening", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const send = (method, path, body) => fetch(base + path, {
  method,
  headers: { "content-type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

try {
  assert.deepEqual(await (await send("GET", "/todos")).json(), []);

  const created = await send("POST", "/todos", { title: "  write tests  " });
  assert.equal(created.status, 201);
  assert.deepEqual(await created.json(), { id: 1, title: "write tests", done: false });

  assert.equal((await (await send("POST", "/todos", { title: "ship", done: true })).json()).id, 2);
  assert.equal((await send("POST", "/todos", { title: "   " })).status, 422);
  assert.equal((await send("POST", "/todos", {})).status, 422);

  const finished = await (await send("GET", "/todos?done=true")).json();
  assert.deepEqual(finished.map((todo) => todo.id), [2]);

  const patched = await send("PATCH", "/todos/1", { done: true });
  assert.equal(patched.status, 200);
  assert.deepEqual(await patched.json(), { id: 1, title: "write tests", done: true });

  assert.equal((await send("DELETE", "/todos/1")).status, 204);
  const missing = await send("GET", "/todos/1");
  assert.equal(missing.status, 404);
  assert.deepEqual(await missing.json(), { detail: "Todo not found" });
} finally {
  server.close();
}
```
