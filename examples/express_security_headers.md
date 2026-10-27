# ExpressSecurityHeaders

A security review of a small Express API found missing security headers and an open CORS policy. Fix both without adding a dependency: only `express` is installed.

Write a function `solution({ allowedOrigins })` that returns a new Express application, and export it with `module.exports = { solution };`. `allowedOrigins` is an array of origins such as `"https://app.example.com"`.

The app has two routes:

- `GET /api/profile` responds `200` with `{"name": "Ada Lovelace"}`, or the name last saved.
- `PUT /api/profile` takes `{"name": <string of 1 to 80 characters>}`, saves it and responds `200` with `{"name": <string>}`. An invalid body responds `422` with `{"detail": <message>}`, malformed JSON responds `400` with `{"detail": "Malformed JSON"}`, and a body over 10 kB responds `413` with `{"detail": "Payload too large"}`.

Any other path responds `404` with `{"detail": "Not found"}`.

Every response, including errors and 404s, carries these headers and no `X-Powered-By` header:

| Header | Value |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` |

CORS:

- A request whose `Origin` is in `allowedOrigins` gets `Access-Control-Allow-Origin` set to that origin. Every response under `/api` carries `Vary: Origin`.
- A request from any other origin, or with no `Origin`, gets no `Access-Control-Allow-Origin` header and is otherwise served normally.
- An `OPTIONS` preflight to any path under `/api/` from an allowed origin responds `204` with `Access-Control-Allow-Methods: GET, PUT`, `Access-Control-Allow-Headers: Content-Type, Authorization` and `Access-Control-Max-Age: 600`. From any other origin it responds `403` with `{"detail": "Origin not allowed"}`.

The tests start the app with `app.listen(0)` and call it with the built-in `fetch`.

```js
const server = solution({ allowedOrigins: ["https://app.example.com"] }).listen(0);
await new Promise((resolve) => server.once("listening", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const secure = (response) => {
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("x-frame-options"), "DENY");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
  assert.equal(response.headers.get("strict-transport-security"), "max-age=31536000; includeSubDomains");
  assert.equal(response.headers.get("content-security-policy"), "default-src 'none'; frame-ancestors 'none'");
  assert.equal(response.headers.get("x-powered-by"), null);
};

try {
  const own = await fetch(base + "/api/profile", { headers: { origin: "https://app.example.com" } });
  secure(own);
  assert.equal(own.headers.get("access-control-allow-origin"), "https://app.example.com");
  assert.match(own.headers.get("vary"), /Origin/);
  assert.deepEqual(await own.json(), { name: "Ada Lovelace" });

  const other = await fetch(base + "/api/profile", { headers: { origin: "https://evil.example" } });
  assert.equal(other.status, 200);
  assert.equal(other.headers.get("access-control-allow-origin"), null);

  const preflight = await fetch(base + "/api/profile", { method: "OPTIONS", headers: { origin: "https://app.example.com", "access-control-request-method": "PUT" } });
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get("access-control-allow-methods"), "GET, PUT");
  assert.equal(preflight.headers.get("access-control-max-age"), "600");
  const blocked = await fetch(base + "/api/profile", { method: "OPTIONS", headers: { origin: "https://evil.example" } });
  assert.equal(blocked.status, 403);

  const put = (body) => fetch(base + "/api/profile", { method: "PUT", headers: { "content-type": "application/json" }, body });
  assert.deepEqual(await (await put(JSON.stringify({ name: "Grace Hopper" }))).json(), { name: "Grace Hopper" });
  assert.deepEqual(await (await fetch(base + "/api/profile")).json(), { name: "Grace Hopper" });
  assert.equal((await put(JSON.stringify({ name: "" }))).status, 422);
  const broken = await put("{");
  secure(broken);
  assert.deepEqual([broken.status, await broken.json()], [400, { detail: "Malformed JSON" }]);
  assert.equal((await put(JSON.stringify({ name: "x".repeat(20000) }))).status, 413);

  const missing = await fetch(base + "/nope");
  secure(missing);
  assert.deepEqual([missing.status, await missing.json()], [404, { detail: "Not found" }]);
} finally {
  server.close();
}
```
