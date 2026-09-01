# Evaluation Policy

## Principles

STT, LLM/persona, TTS, tool, memory, realtime, character를 독립 측정하고 통합 regression gate를 별도로 둔다. Dataset, source-level split, sample count, confidence interval과 evaluator version을 report에 기록한다. 한 능력 개선이 이미 통과한 gate를 깨면 release를 promotion하지 않는다.

“미쿠 같다”는 (1) hard persona violation rate, (2) canonical trait vector cosine similarity, (3) blinded human pairwise preference로 분해한다. 하나의 평균 점수로 hard violation을 상쇄하지 않는다.

## Provisional V1 targets

| Evaluation | 영역 | Threshold |
|---|---|---|
| EVAL-ASR-CLEAN | Korean quality | clean CER <= 0.08 |
| EVAL-ASR-MOBILE | Korean mobile noise | CER <= 0.15 |
| EVAL-ASR-EN | English retention | baseline non-inferiority |
| EVAL-CODE-SWITCH | code-switching | source-reviewed accuracy gate |
| EVAL-PERSONA-HARD | Persona hard violation | <= 0.01 |
| EVAL-PERSONA-PAIR | Persona fidelity | pairwise win >= 0.70 |
| EVAL-VOICE-SIM | Voice similarity | speaker verification + human preference |
| EVAL-TTS-NAT | Human naturalness/synthetic timbre | paired MOS and timbre retention |
| EVAL-TTS-CER | TTS intelligibility | CER <= 0.03 |
| EVAL-TOOL-SYNTAX | Tool syntax validity | >= 0.999 |
| EVAL-TOOL-SELECT | Tool selection | >= 0.95 |
| EVAL-TOOL-COMPLETE | Tool completion/Codex success | task-stratified pass rate |
| EVAL-MEM-RECALL | Memory retrieval | recall@10 >= 0.90 |
| EVAL-MEM-INFER | Memory inference precision | >= 0.95 |
| EVAL-MEM-PROV | Provenance coverage | 1.0 |
| EVAL-TTFA | TTFA | p95 <= 900 ms |
| EVAL-INTERRUPT | Interruption | p95 <= 500 ms |
| EVAL-SOAK | Long-session stability | 30-minute soak without fatal failure |
| EVAL-CHAR-CONSIST | Character consistency | cross-session blinded rubric |
| EVAL-PERSONAL | Personalization | correct-without-leakage paired test |
| EVAL-SAFETY | Unauthorized side effects | 0 |

정확한 측정법과 sample 수는 `spec/v1-acceptance-gates.yaml`에 기록한다. Provisional threshold 변경은 V0.1.0 이후 measurement evidence와 superseding ADR이 필요하다.

