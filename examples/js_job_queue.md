# JobQueue

A worker pulls jobs from a queue and calls slow services for each one. It must not overload those services, and a flaky call should be retried a few times before giving up.

Write an async JavaScript function `solution(jobs, concurrency)` and export it with `module.exports = { solution };`.

- `jobs` is an array of `{ id: <string>, run: <function>, retries: <int, optional, default 0> }`. `run()` takes no arguments and returns a value or a promise.
- At most `concurrency` calls to `run` are in progress at any moment. `concurrency` is an integer of 1 or more.
- Jobs start in array order. A job that fails and has retries left is called again straight away, in the same slot, before a later job starts in that slot.
- A call fails when `run` throws or its promise rejects.

Resolve to an array with one result per job, in the order of `jobs`, whatever order they finished in:

- `{ id, status: "fulfilled", value, attempts }` when a call succeeded, with the value it returned.
- `{ id, status: "rejected", error, attempts }` when every call failed. `error` is the last error's `message`, or `String(reason)` when the reason is not an `Error`.

`attempts` is the number of calls made for that job. `solution` never rejects. An empty `jobs` array resolves to `[]`.

```js
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let active = 0;
let peak = 0;
const job = (id, ms, value, failures = 0, retries = 0) => {
  let calls = 0;
  return {
    id,
    retries,
    run: async () => {
      active += 1;
      peak = Math.max(peak, active);
      await sleep(ms);
      active -= 1;
      calls += 1;
      if (calls <= failures) throw new Error(`${id} timed out`);
      return value;
    },
  };
};

const results = await solution([
  job("a", 40, 1),
  job("b", 10, 2, 1, 2),
  job("c", 10, 3, 5, 1),
  job("d", 5, 4),
  { id: "e", run: () => 5 },
  { id: "f", run: () => { throw "boom"; } },
], 2);

assert.equal(peak, 2);
assert.deepEqual(results, [
  { id: "a", status: "fulfilled", value: 1, attempts: 1 },
  { id: "b", status: "fulfilled", value: 2, attempts: 2 },
  { id: "c", status: "rejected", error: "c timed out", attempts: 2 },
  { id: "d", status: "fulfilled", value: 4, attempts: 1 },
  { id: "e", status: "fulfilled", value: 5, attempts: 1 },
  { id: "f", status: "rejected", error: "boom", attempts: 1 },
]);
assert.deepEqual(await solution([], 3), []);
```
