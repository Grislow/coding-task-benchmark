## Python

Judge against what an experienced Python developer writes for a task of this size. A short, direct solution that uses the language and the standard library well is the target. More structure is not better.

- **PY-STDLIB** (major): hand-rolls what a built-in or the standard library already does, such as counting into a dict instead of `collections.Counter`, a manual max loop instead of `max(..., key=...)`, a hand-written binary search instead of `bisect`, or a manual heap instead of `heapq`.
- **PY-DATA** (major): the wrong data structure for the access pattern, such as `in` on a list inside a loop, repeated sorting or slicing in a loop, or `list.pop(0)` where a `deque` fits.
- **PY-IDIOM** (minor): a non-idiomatic construct, such as `range(len(x))` where `enumerate` or `zip` fits, a manual index counter, `== True`, `+=` string building in a loop, or a comprehension used only for its side effects.
- **PY-NAME** (minor): a name that describes a type or nothing (`lst`, `tmp`, `res`, `d`, `flag`) instead of what the value means. Parameter names that the task statement fixes, such as `A` or `N`, are exempt.
- **PY-FLOW** (minor): nesting or flag variables where a guard clause, an early return or a single expression reads directly.
- **PY-FUNC** (major): one function mixes levels of detail that should be separate, or a helper, class or wrapper exists that is used once and adds no name worth having.
- **PY-OVER** (major): speculative generality: unused parameters or options, configuration for values that never change, or defensive checks that the task's stated constraints already rule out.
- **PY-EDGE** (minor): edge cases from the constraints (empty input, one element, limits) are patched with scattered special cases where a different structure would cover them naturally.
