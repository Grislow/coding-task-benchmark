# ConfigMerge

A service reads its configuration from several layers: built-in defaults, a config file, then per-environment overrides. String values may reference environment variables.

Write a JavaScript function `solution(layers, env)` and export it with `module.exports = { solution };`.

- `layers` is an array of plain objects, merged from first to last, so a later layer wins.
- Two plain objects at the same key are merged key by key, at any depth. Any other value, including an array, replaces what was there.
- A `null` value in a later layer removes that key from the result.
- After merging, every string in the result, at any depth and inside arrays, has each `${NAME}` replaced by `env[NAME]`. `${NAME:-fallback}` uses `fallback` when `NAME` is missing or empty in `env`. Names are made of `A-Z`, `0-9` and `_`.
- A reference with no value and no fallback throws an `Error` whose message is `Missing environment variable NAME at path`, where `path` joins the keys and array indexes with dots, such as `db.replicas.1`. When several are missing, report the first one met walking the result depth first, in key order.
- Do not change `layers` or `env`.

Return the merged object.

```js
const defaults = { port: 8080, db: { host: "localhost", pool: 5, replicas: [] }, features: { search: true, beta: false } };
const file = { db: { host: "${DB_HOST}", user: "${DB_USER:-app}" }, features: { beta: null }, tags: ["svc-${REGION:-eu}"] };
const prod = { port: 443, db: { pool: 20, replicas: ["${DB_HOST}", "replica-2"] } };

assert.deepEqual(solution([defaults, file, prod], { DB_HOST: "db.internal", REGION: "" }), {
  port: 443,
  db: { host: "db.internal", pool: 20, replicas: ["db.internal", "replica-2"], user: "app" },
  features: { search: true },
  tags: ["svc-eu"],
});
assert.equal(defaults.db.host, "localhost");
assert.equal("beta" in defaults.features, true);
assert.throws(() => solution([defaults, file], {}), { message: "Missing environment variable DB_HOST at db.host" });
assert.deepEqual(solution([], {}), {});
```
