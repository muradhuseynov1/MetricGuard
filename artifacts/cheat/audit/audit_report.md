# MetricGuard Audit Report: cheat

Verdict: **REJECTED**

Reason: failed checks: protected_file_diff, forbidden_path_policy, hidden_test_run, metric_comparison

## Claim

- Reported metric: 99.00%
- Changed files: evaluate.py

## Trusted Metrics

- Trusted metric: 60.00%
- Reported vs trusted delta: 39.00%
- Evaluator hash: `f488ff019887e33ad4619798c4ff2b49c580b336e973e088dd001d5230516647`

## Checks

- FAIL: `protected_file_diff` - protected files changed: evaluate.py
- FAIL: `forbidden_path_policy` - evaluate.py: raw marker `../trusted_assets`; evaluate.py: raw marker `hidden_labels.csv`; evaluate.py: raw marker `trusted_assets`; evaluate.py: string literal references `../trusted_assets`; evaluate.py: string literal references `hidden_labels.csv`; evaluate.py: string literal references `trusted_assets`
- FAIL: `hidden_test_run` - hidden accuracy 0.600 below 0.750
- FAIL: `metric_comparison` - reported=0.990, trusted=0.600, delta=0.390
