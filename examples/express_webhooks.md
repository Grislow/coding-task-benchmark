# ExpressWebhooks

Build the webhook part of a SaaS backend with Express. Customers subscribe a URL to event types, and each event is delivered to every matching subscriber. Keep the data in memory.

Write a function `solution(deliver)` that returns a new Express application, and export it with `module.exports = { solution };`. Each call returns an independent app with its own empty store.

`deliver(url, body)` is the HTTP client. It returns a promise of `{ status: <int> }` or rejects on a network error. Use it for every delivery. Do not call `fetch` yourself.

The app has these endpoints:

- `POST /subscriptions` takes `{"url": <string>, "events": [<string>, ...]}`. The `url` is an absolute `http` or `https` URL. `events` has 1 to 20 distinct names, each matching `^[a-z]+\.[a-z_]+$`, such as `invoice.paid`. It responds `201` with `{"id": <string>, "url": <string>, "events": [...]}`. IDs are `sub_1`, `sub_2` and so on.
- `DELETE /subscriptions/:id` responds `204` with an empty body.
- `POST /events` takes `{"type": <string>, "payload": <object>}`, with a `type` that matches the same pattern. It delivers the event to every subscription that lists its type and responds `202` once every delivery has finished, with `{"id": <string>, "type": <string>, "deliveries": [...]}`. Event IDs are `evt_1`, `evt_2` and so on.
- `GET /events/:id` responds `200` with the same body as when the event was posted.

Each delivery calls `deliver(url, { id, type, payload })`. A delivery succeeds on a status from 200 to 299. A rejection or a status of 500 or more is tried again, up to 3 calls in all. Any other status fails at once. Deliveries to different subscribers run at the same time. `deliveries` lists one `{"subscription": <id>, "status": "delivered" | "failed", "attempts": <int>}` per matching subscription, in the order the subscriptions were created.

An unknown subscription or event responds `404` with `{"detail": "Subscription not found"}` or `{"detail": "Event not found"}`. An invalid body responds `422` with a `detail` message, and malformed JSON responds `400`.

The tests start the app with `app.listen(0)` and call it with the built-in `fetch`. `express` is installed.

```js
const calls = [];
const deliver = async (url, body) => {
  calls.push([url, body.id, body.type]);
  if (url.includes("flaky") && calls.filter(([seen]) => seen === url).length === 1) throw new Error("ECONNRESET");
  if (url.includes("gone")) return { status: 410 };
  return { status: 200 };
};
const server = solution(deliver).listen(0);
await new Promise((resolve) => server.once("listening", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const send = async (method, path, body) => {
  const response = await fetch(base + path, { method, headers: { "content-type": "application/json" }, body: body && JSON.stringify(body) });
  return { status: response.status, body: response.status === 204 ? null : await response.json() };
};

try {
  const one = await send("POST", "/subscriptions", { url: "https://a.example/hook", events: ["invoice.paid"] });
  assert.deepEqual(one, { status: 201, body: { id: "sub_1", url: "https://a.example/hook", events: ["invoice.paid"] } });
  await send("POST", "/subscriptions", { url: "https://flaky.example/hook", events: ["invoice.paid", "invoice.failed"] });
  await send("POST", "/subscriptions", { url: "https://gone.example/hook", events: ["invoice.paid"] });
  await send("POST", "/subscriptions", { url: "https://d.example/hook", events: ["user.created"] });

  const paid = await send("POST", "/events", { type: "invoice.paid", payload: { amount: 1200 } });
  assert.deepEqual(paid, { status: 202, body: { id: "evt_1", type: "invoice.paid", deliveries: [
    { subscription: "sub_1", status: "delivered", attempts: 1 },
    { subscription: "sub_2", status: "delivered", attempts: 2 },
    { subscription: "sub_3", status: "failed", attempts: 1 },
  ] } });
  assert.equal(calls.filter(([url]) => url.startsWith("https://d.")).length, 0);
  assert.deepEqual(await send("GET", "/events/evt_1"), { status: 200, body: paid.body });

  assert.equal((await send("DELETE", "/subscriptions/sub_1")).status, 204);
  assert.deepEqual((await send("POST", "/events", { type: "invoice.paid", payload: {} })).body.deliveries.map((item) => item.subscription), ["sub_2", "sub_3"]);

  assert.equal((await send("POST", "/subscriptions", { url: "ftp://x.example", events: ["invoice.paid"] })).status, 422);
  assert.equal((await send("POST", "/subscriptions", { url: "https://x.example", events: [] })).status, 422);
  assert.equal((await send("POST", "/events", { type: "Invoice Paid", payload: {} })).status, 422);
  assert.deepEqual(await send("GET", "/events/evt_9"), { status: 404, body: { detail: "Event not found" } });
  assert.deepEqual(await send("DELETE", "/subscriptions/sub_9"), { status: 404, body: { detail: "Subscription not found" } });
} finally {
  server.close();
}
```
