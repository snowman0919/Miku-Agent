# Test Intent

| Test | Protected requirement | Failure mode | Decision value |
|---|---|---|---|
| Schema valid/invalid contract cases | Rights, evidence, revocation, approval, codec, tool authority boundaries | Architecture-invalid data is accepted or valid data rejected | Prevents unsafe state crossing service boundaries |
| Product lock invariants | Fixed V0.0.0 technology and scope decisions | A silent edit enables public/server/WebRTC/privileged behavior | Detects unauthorized architecture drift |
| Document traceability | Every accepted ADR has document/spec/schema or evaluation evidence | Decision exists only in prose or loses validation path | Makes later superseding changes reviewable |
| ADR/document consistency | Accepted ADR and its source document retain the same semantic anchors | Prose silently contradicts or omits a locked decision | Fails architecture drift before implementation |
| Release manifest integrity | Recorded document hashes and ADR inventory match the release content | Manifest looks valid but identifies stale evidence | Makes the release evidence independently reproducible |
| Repository safety | No secret, raw media, model weight or public remote | Sensitive/rights-bearing artifact is staged or pushed | Protects private research and credentials |
