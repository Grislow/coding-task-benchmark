# CurrencyConverter

A payments service gets exchange rates from a provider as a list of pairs, not as a full table. Convert amounts between any two currencies the rates connect.

Write a function `solution(rates, conversions)`.

- `rates` is a list of tuples `(source, target, rate)`, meaning 1 unit of `source` buys `rate` units of `target`. The reverse rate is `1 / rate`. Rates are consistent, so every path between two currencies gives the same result.
- `conversions` is a list of tuples `(amount, source, target)`.

Return a list with one entry per conversion, in order: the converted amount rounded to 2 decimal places, or `None` when the rates do not connect the two currencies. Converting a currency to itself returns the amount rounded to 2 decimal places, even when that currency has no rates. Currency codes are case sensitive.

There are at most 200 currencies, 2,000 rates and 10,000 conversions.

```python
rates = [("EUR", "USD", 1.1), ("USD", "JPY", 150.0), ("GBP", "EUR", 1.2)]
assert solution(rates, [(10, "EUR", "JPY")]) == [1650.0]
assert solution(rates, [(1650, "JPY", "EUR")]) == [10.0]
assert solution(rates, [(5, "GBP", "USD"), (3, "USD", "GBP")]) == [6.6, 2.27]
assert solution(rates, [(1, "EUR", "CHF"), (7.456, "CHF", "CHF")]) == [None, 7.46]
```
