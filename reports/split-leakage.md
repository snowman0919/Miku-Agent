# Split and Leakage Audit

- Policy: `source-split-v1`, SHA-256 group assignment.
- Assignments: train 10, validation 1, test 3, eval 6.
- Frozen eval manifest: `eval-holdouts-v1`, SHA-256 `b8be7a1091a57ab933e4d135ecf041d8073856138fbfdb243bf2c35ea37003e8`.
- Direct/transitive lineage leakage findings: 0.

Tests additionally construct a deliberate train→eval lineage edge and confirm that audit/export fail closed. Near-duplicate acoustic/semantic detection은 아직 구현되지 않아 0 findings를 전체 dedup PASS로 확대하지 않는다.
