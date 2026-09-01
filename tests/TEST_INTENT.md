# Test Intent

| Test | Protected requirement | Failure mode | Decision value |
|---|---|---|---|
| Schema valid/invalid contract cases | Rights, evidence, revocation, approval, codec, tool authority boundaries | Architecture-invalid data is accepted or valid data rejected | Prevents unsafe state crossing service boundaries |
| Product lock invariants | Fixed V0.0.0 technology and scope decisions | A silent edit enables public/server/WebRTC/privileged behavior | Detects unauthorized architecture drift |
| Document traceability | Every accepted ADR has document/spec/schema or evaluation evidence | Decision exists only in prose or loses validation path | Makes later superseding changes reviewable |
| Repository safety | No secret, raw media, model weight or public remote | Sensitive/rights-bearing artifact is staged or pushed | Protects private research and credentials |

