# Subagent Orchestration Report

## Accepted Window 001

- Attempts 59, accepted 30, first-pass accepted 24.
- Command Code accepted 20: `poolside/laguna-s-2.1-free` 12, `meituan/LongCat-2.0:free` 8.
- OpenCode accepted 10: `opencode/nemotron-3-ultra-free` 10.
- Actual ratio 2.0, target ratio 2:1.
- Mean/p50/p95 latency: 47,740 / 25,464 / 147,024 ms.
- Failures excluded from ratio: `OUTPUT_SCHEMA_INVALID` 14, `PROVIDER_UNAVAILABLE` 14,
  `AGENT_RUNTIME_ERROR` 1.

Command Code generation을 OpenCode가 독립 비평했고 deterministic schema/hash 검사 후 parent가
200 seed와 10 critique를 직접 adjudicate했다. 194 seed를 speech render bundle 설계에 사용하고
문법·오탈자·부자연스러운 code switch 6개는 quarantine했다.

채택한 규칙은 raw/spoken/normalized 분리, 숫자·단위·약어 발음 명시, 관계/말높임 metadata,
종결·길이 분포, exact/family dedup, 문법/code-switch quarantine이다. Receipt와 provider output은
`$MIKU_DATA_ROOT/jobs/subagents/window-001`에 있고 Git에는 넣지 않았다.

Paid Command Code provider는 HTTP 429 quota로 실패했다. 공개 입력만 free fallback에 보냈고,
credential, private raw audio, 권리 미확인 원문과 repository secret은 보내지 않았다.

## Diverse Seed Pilot 002

- 2026-09-03 live model list의 free 모델은 Laguna와 LongCat 두 개뿐이었다.
- 공개 추상 prompt만 `provider_default` retention으로 보낸 Command Code 6건은 모두 제외했다.
  실패는 ZDR upstream 없음 2, upstream 520/503 2, output schema/JSON invalid 2다.
- OpenCode 1건은 schema-valid original Korean seed 12개를 만들었고 parent가 전부 직접 읽었다.
  Output/receipt file SHA-256은 `3e1ba1d7a9c7caefcb3c7f7cc78281d850fd6b24971e02e9d67d75f63b876f37` /
  `2c0b5ad48bc7118d226619d336bf79a8b096482718ff32eda0eea1c5bc21a94a`다.
- 기존 20,000 candidate와 normalized exact, character/token Jaccard 0.8, pinned E5 cosine
  0.98/0.99 교차 pair는 모두 0이었다. Pilot 12개 내부 pair도 모두 0이고 기존 corpus와의
  최고 cosine은 0.933519다.
- 이 결과는 prompt design의 12/12 semantic yield evidence일 뿐 accepted subordinate job이나
  canonical corpus로 계산하지 않는다. 사용하면 기존 20:10 비율과 independent cross-review를
  유지할 수 없기 때문이다. Output과 receipt는 Git 밖 `window-002-pilot`에 보존한다.

## Diverse Window 003

- Accepted job은 Command Code 2, OpenCode 1이며 실제 비율 2.0으로 2:1 target을 충족했다.
  Laguna와 LongCat이 각각 생성하고 Nemotron이 독립 비평했다.
- 제외된 job 3건은 JSON truncation 1, upstream unavailable 1, critic schema 초과 1이다.
- Parent가 생성 20개를 모두 읽고, 검증되지 않은 수치·고정 경로/날짜·기술 오류·부자연스러운
  말투가 있는 13개를 제외해 7개만 candidate로 남겼다.
- 7개는 기존 candidate 20,000개와 normalized exact 및 Jaccard 0.8 match가 0이다. Pinned E5
  cosine 0.98/0.99의 cross/within match도 0이며 최대 cross cosine은 0.910924다.
- Adjudication/seed/duplicate report SHA-256은
  `0c56babc7e5a4b04f3b6caf38c3e1923770a7c01b5a92052c6ff18f0dabe9ca1` /
  `768224d65d96fcaa2d992a6c0f9efb39945fd2fa1cf578ce82df6be040d79e19` /
  `be0c195a8cd619cd73518aa1dab851418dc4b9940eaca1cbb758bdd622ccfbfb`다.
- 첫 critic이 repository cwd에 요청하지 않은 `critique_result.json`을 썼다. Parent가 이를 Git 밖
  evidence 폴더로 옮겼고(SHA-256 `76c84c24b5157c46d35eaf8aa929db8896d4d25246d70f5c028cc16116364eab`),
  OpenCode wrapper의 기본 cwd를 임시 격리 디렉터리로 바꿨다. 명시적 workspace write는 새 opt-in이 필요하다.
- 7개는 다양성 증거일 뿐 canonical 또는 training corpus로 계산하지 않는다. Raw output과 receipt는
  Git 밖 `window-003-diverse`에 보존한다.
