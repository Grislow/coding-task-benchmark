## Comments

Code explains itself through names and structure. A comment earns its place only when it states something the code cannot: a constraint, an invariant, or why a non-obvious approach was chosen. Missing comments and docstrings are never a finding. Never treat a comment as a reason to think better of the code.

- **CMT-WHAT** (major): a comment restates what the code on that line or the next lines does, such as `# loop over the items` or `# return the result`.
- **CMT-NAME** (major): a comment explains a name, value or block that a better name or a small named function would make clear.
- **CMT-NOISE** (minor): commented-out code, section banners, a docstring that repeats the function name or signature, or a comment that is wrong about the code.
