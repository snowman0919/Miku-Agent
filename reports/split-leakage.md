# Split and Leakage Audit

- Policy: `source-split-v1`, source/derivative-family 경계.
- Frozen evaluation groups: 6.
- TTS 1,000, STT 1,000, persona prompts 1,000, agentic tasks 500, duplex 500,
  normalization 1,000으로 모두 non-empty다.
- Frozen eval의 train export 포함과 direct/transitive lineage leakage findings: 0.
- Empty evaluation source의 populated/frozen 전환은 DB trigger가 거부한다.

SHA-256/lineage audit는 통과했지만 acoustic/semantic near-duplicate 검사는 아직 실행하지 않아
0 findings를 전체 dedup PASS로 확대하지 않는다.
