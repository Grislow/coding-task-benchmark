# QuickSlug

A blog needs URL slugs for its post titles.

Write a JavaScript function `solution(title)` and export it with `module.exports = { solution };`. Return the slug of `title`:

- Lowercase it.
- Turn every run of characters other than `a-z` and `0-9` into a single `-`.
- Remove any `-` at the start or end.

A title with no letters or digits returns an empty string.

```js
assert.equal(solution("Hello, World!"), "hello-world");
assert.equal(solution("  Node.js 22 -- what's new?  "), "node-js-22-what-s-new");
assert.equal(solution("!!!"), "");
```
