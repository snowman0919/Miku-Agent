# Test Intent

| Test | Protected requirement | Failure mode | Decision value |
|---|---|---|---|
| Schema valid/invalid contract cases | Rights, evidence, revocation, approval, codec, tool authority boundaries | Architecture-invalid data is accepted or valid data rejected | Prevents unsafe state crossing service boundaries |
| Product lock invariants | Fixed V0.0.0 technology and scope decisions | A silent edit enables public/server/WebRTC/privileged behavior | Detects unauthorized architecture drift |
| Document traceability | Every accepted ADR has document/spec/schema or evaluation evidence | Decision exists only in prose or loses validation path | Makes later superseding changes reviewable |
| ADR/document consistency | Accepted ADR and its source document retain the same semantic anchors | Prose silently contradicts or omits a locked decision | Fails architecture drift before implementation |
| Release manifest integrity | Recorded document hashes and ADR inventory match the release content | Manifest looks valid but identifies stale evidence | Makes the release evidence independently reproducible |
| Repository safety | No secret, raw media, model weight or public remote | Sensitive/rights-bearing artifact is staged or pushed | Protects private research and credentials |
| Self-reference regression | Manifest Format 2 forbids fields that try to record its own release commit | A future edit reintroduces an impossible fixed-point SHA | Preserves non-self-referential release identity |
| Definition binding | Definition commit exists, is an ancestor and is the release commit parent | Manifest binds nonexistent or unrelated source | Makes source identity cryptographically meaningful |
| Historical document hash | Hashes are computed from definition commit Git blobs | Validator accidentally binds mutable working-tree content | Keeps old release evidence reproducible after later edits |
| V0.0.0 immutability | Historical ledger equals the actual local annotated tag | Published baseline is silently moved or ledger is falsified | Prevents correction work from rewriting V0.0.0 |
| Offline independence | Validator passes with a PATH that contains Git but no gh executable | Offline validation regains a hidden GitHub dependency | Keeps past releases verifiable without network or provider state |
| Foundry atomic ingest and recovery | Canonical objects and SQLite references become visible together after recoverable intent processing | Crash or FK failure leaves an accepted dangling row or unexplained object | Prevents silent corpus corruption across filesystem/DB boundaries |
| Foundry content integrity | Export trusts bytes only after SHA-256 verification | Mutated canonical bytes are silently relabelled or exported | Keeps content-addressed identity meaningful |
| Rights promotion gate | Cleared evidence, human authority, quality and review independently gate training | Unknown/restricted source or agent self-promotion reaches training | Enforces data governance at the transaction boundary |
| Source-group split isolation | Stable group hashing and immutable frozen assignments prevent sample-level leakage | Derivatives or evaluation families cross train/eval splits | Preserves honest evaluation evidence |
| Append-only review | Expected revision protects concurrent decisions | Last writer silently overwrites a prior review | Keeps human adjudication auditable |
| Remote 5090 lease | Remote work requires a job-bound source grant and never writes canonical state | GPU availability alone triggers an unauthorized remote side effect | Protects canonical ownership and external permission boundaries |
| Effective hours accounting | Physical speech, weighted speech and singing auxiliary totals remain separate | Singing or unresolved-rights audio inflates effective speech hours | Prevents misleading training-readiness claims |
| Audio decode probe | Quality metrics come from decoded immutable bytes with explicit decoder constraints | Header-only metadata or destructive normalization hides corrupt/changed audio | Grounds intake quality evidence without replacing the source object |
