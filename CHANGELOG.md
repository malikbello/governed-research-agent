# Changelog

## 0.1.1

- Added a real test suite (`tests/test_governance.py`) covering budget enforcement, retry/backoff, circuit-breaker tripping, timeouts, and the two additions below. Previously the library shipped with zero tests.
- Added a `py.typed` marker so type checkers (mypy/pyright) treat the installed package as typed, per PEP 561.
- Added CI (`.github/workflows/ci.yml`) running the test suite on Python 3.12 and 3.13 on every push/PR, and gated `publish.yml` on the same test suite passing before a release can build.
- `init_governance()` gained `non_retryable`: a tuple of exception types that are raised immediately instead of being retried, so a deterministic failure (bad auth, malformed input) doesn't burn retry budget and wall-clock time repeating a call that can't succeed.
- `init_governance()` gained `max_total_time_s`: an optional cap on cumulative wall-clock time across every governed call an agent instance makes, since a per-attempt `timeout_s` alone doesn't bound how much real time a long-running agent can spend.
- `governance_report()` now echoes back the configured limits (`max_calls`, `max_retries_per_call`, `timeout_s`, `max_total_time_s`) and total `elapsed_s`, not just the counters against them -- an audit trail should show what it was auditing against.

## 0.1.0

Initial release.
