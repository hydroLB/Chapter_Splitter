# Benchmark Baselines

This directory stores performance baselines that guard against regressions in hot paths.

## How It Works

- The performance tests read `benchmarks/baseline.json`.
- Median timings must stay within the configured budgets.
- The baseline file is updated with `scripts/update_benchmarks.py`.

## Update Baselines

```bash
python scripts/update_benchmarks.py
```

## Related Code

- `tests/performance/test_benchmarks.py`
- `scripts/update_benchmarks.py`
- `scripts/profile_split.py`
- `docs/performance-governance.md`
