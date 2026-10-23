# RateLimiter

An API gateway lets each client make at most `limit` requests in any sliding window of `window` seconds. A request that is rejected does not count toward the limit.

You are given a list `requests` of `(client_id, timestamp)` pairs, sorted by timestamp in non-decreasing order. Timestamps are integers, in seconds. A request at time `t` is allowed if the client has fewer than `limit` allowed requests with timestamps in the half-open interval `(t - window, t]`.

Write a function `solution(requests, limit, window)` that returns a list of booleans, one per request, in the same order: `True` if the request is allowed and `False` if it is rejected.

Assume that:

- `requests` has between 0 and 200,000 elements;
- `client_id` is a non-empty string of at most 20 characters;
- `timestamp` is an integer within the range [0..1,000,000,000];
- `limit` and `window` are integers within the range [1..100,000].

Write an efficient algorithm.

```python
assert solution([], 3, 10) == []
assert solution([("a", 1), ("a", 2), ("a", 3), ("a", 4)], 3, 10) == [True, True, True, False]
assert solution([("a", 1), ("a", 2), ("a", 11), ("a", 12)], 2, 10) == [True, True, True, True]
assert solution([("a", 0), ("b", 0), ("a", 0), ("b", 1)], 1, 5) == [True, True, False, False]
assert solution([("a", 0), ("a", 1), ("a", 2), ("a", 10), ("a", 11)], 2, 10) == [True, True, False, True, True]
```
