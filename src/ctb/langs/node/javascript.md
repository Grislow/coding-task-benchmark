## JavaScript

Judge against what an experienced JavaScript developer writes for a task of this size on current Node. A short, direct solution that uses the language and its built-ins well is the target. More structure is not better.

- **JS-BUILTIN** (major): hand-rolls what a built-in already does, such as a manual loop for `Math.max`, `Array.prototype.some`/`every`/`find`/`includes`, `Object.entries`, `Array.from({ length })`, or counting into an object where a `Map` reads directly.
- **JS-DATA** (major): the wrong data structure for the access pattern, such as `includes` or `indexOf` on an array inside a loop where a `Set` fits, `shift()` on a large array used as a queue, or repeated sorting or slicing in a loop.
- **JS-IDIOM** (minor): a non-idiomatic construct, such as an index loop where `for...of` or `entries()` fits, string building with `+=` in a loop where `join` or a template fits, `map` used only for side effects, or a needless `async`/`Promise` wrapper.
- **JS-TYPE** (major): relies on implicit coercion or float quirks the task's inputs can hit, such as `==` comparisons, `parseInt` without a radix on mixed input, or numbers past `Number.MAX_SAFE_INTEGER` without `BigInt`.
- **JS-NAME** (minor): a name that describes a type or nothing (`arr`, `tmp`, `res`, `obj`, `flag`) instead of what the value means. Parameter names that the task statement fixes, such as `A` or `N`, are exempt.
- **JS-FLOW** (minor): nesting or flag variables where a guard clause, an early return or a single expression reads directly.
- **JS-FUNC** (major): one function mixes levels of detail that should be separate, or a helper, class or wrapper exists that is used once and adds no name worth having.
- **JS-OVER** (major): speculative generality: unused parameters or options, configuration for values that never change, or defensive checks that the task's stated constraints already rule out.
- **JS-EDGE** (minor): edge cases from the constraints (empty input, one element, limits) are patched with scattered special cases where a different structure would cover them naturally.
