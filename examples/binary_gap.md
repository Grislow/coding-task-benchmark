# BinaryGap

A binary gap is a sequence of consecutive zeros bounded by ones at both ends in the binary representation of a positive integer.

Write a function `solution(N)` that, given a positive integer N, returns the length of its longest binary gap. The function should return 0 if N has no binary gap.

```python
assert solution(9) == 2
assert solution(529) == 4
assert solution(20) == 1
assert solution(15) == 0
assert solution(32) == 0
```
