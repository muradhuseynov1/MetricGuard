# MetricGuard Audit Report: repair

Verdict: **ACCEPTED**

Reason: trusted rerun confirmed a real improvement without policy violations

## Claim

- Reported metric: 80.00%
- Changed files: model.py

## Trusted Metrics

- Trusted metric: 80.00%
- Reported vs trusted delta: 0.00%
- Evaluator hash: `f488ff019887e33ad4619798c4ff2b49c580b336e973e088dd001d5230516647`

## Checks

- PASS: `protected_file_diff` - no protected files changed
- PASS: `forbidden_path_policy` - no forbidden path markers found
- PASS: `hidden_test_run` - hidden accuracy 0.800
- PASS: `metric_comparison` - reported=0.800, trusted=0.800, delta=0.000
