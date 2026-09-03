# Split and Leakage Audit

- Policy: `source-split-v1`, source/derivative-family 경계.
- Frozen evaluation groups: 6.
- TTS 1,000, STT 1,000, persona prompts 1,000, agentic tasks 500, duplex 500,
  normalization 1,000으로 모두 non-empty다.
- Frozen eval의 train export 포함과 direct/transitive lineage leakage findings: 0.
- Empty evaluation source의 populated/frozen 전환은 DB trigger가 거부한다.

SHA-256/lineage audit와 pinned E5 cosine 0.98/0.99 교차 검사는 통과했다. Speech
candidate 20,000↔TTS eval 1,000, accepted Duplex 2,000↔Duplex eval 500,
accepted Agentic 1↔Agentic eval 500의 semantic pair는 모두 0이다. 실제 accepted target
audio가 없어 acoustic near-duplicate 검사는 아직 실행하지 않았으므로 0 findings를 전체
multimodal dedup PASS로 확대하지 않는다.
