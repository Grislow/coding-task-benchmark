# DependencyOrder

A monorepo build tool needs to know the order in which to build its packages. A package can only be built after every package it depends on.

Write a function `solution(packages)`. `packages` is a dict from a package name to the list of package names it depends on.

Return the list of package names in build order:

- Every package comes after all of its dependencies.
- When several packages are ready to build at the same time, the one whose name sorts first goes first.
- A dependency that is not a key of `packages` is published elsewhere. Leave it out of the result and treat it as already built.
- A package listed twice in the same dependency list counts once.

If the dependencies form a cycle, raise `ValueError` with a message that names the packages in one cycle in order, for example `"cycle: api -> db -> api"`. Start the cycle at the name that sorts first.

There are at most 10,000 packages and 100,000 dependency edges.

```python
import pytest

assert solution({"web": ["api", "ui"], "api": ["db", "requests"], "ui": [], "db": []}) == ["db", "api", "ui", "web"]
assert solution({"b": [], "a": [], "c": ["a", "a"]}) == ["a", "b", "c"]
assert solution({}) == []
with pytest.raises(ValueError, match=r"^cycle: api -> db -> api$"):
    solution({"web": ["api"], "api": ["db"], "db": ["api"]})
```
