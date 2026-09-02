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
| GPU worker package integrity | Job/input manifests bind exact bytes and package-local paths | Corruption, traversal or symlink escape reaches a transform | Prevents untrusted package data from escaping the staged worker boundary |
| GPU worker atomic state and recovery | Only complete, hash-manifested outputs enter completed; stale work is recoverable | Partial output is mistaken for a completed dataset result | Gives the canonical foundry an auditable transfer boundary |
| GPU exclusivity and OOM bound | OS file locking serializes work and OOM retry has an explicit cap | Concurrent jobs contend for VRAM or retry forever | Protects the single-GPU node and makes failure deterministic |
| GPU worker canonical-write prohibition | Worker output cannot contain rights/training/split decisions | A technical score silently becomes canonical acceptance | Preserves RTX 3080 control-plane ownership |
| GPU model immutability | Worker model profiles use immutable revisions and hashes | A floating model changes transform meaning under the same task name | Keeps fingerprints and benchmark evidence reproducible |
