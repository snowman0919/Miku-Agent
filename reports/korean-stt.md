# Korean STT — Zeroth Intake

2026-09-03 처리 중 기록이며 training acceptance 보고가 아니다.

## Source와 권리 근거

- [OpenSLR SLR40](https://openslr.org/40/)의 Zeroth-Korean corpus를 공식 mirror에서 획득했다.
- 공식 페이지는 CC BY 4.0과 train 22,263개/105명/51.6시간을 명시한다.
- Canonical source: `f89e3b13-e9ee-5a98-b14f-045a68e5a106`, `source_type=stt`,
  `character_id=non-target`, family `openslr-slr40-zeroth-korean-train-v1`.
- 공식 페이지를 immutable object로 보존했다. SHA-256:
  `3e7664fc9af1fc2852b04b4ee25c6d4fab2abc9c733c0d2dff7ce23d87f2b146`.
- Rights는 attribution을 조건으로 private ML training/derivative scope를 기록했다.
  Public redistribution은 하지 않는다. Frozen train split은 공식 test와 별도다.
- Source는 현재 `unscored/unreviewed/quarantine`이다. Model 결과만으로 승격하지 않는다.

## 원본과 실제 디코드

- Archive: 10,339,720,618 bytes. 실제 수신 파일의 SHA-256:
  `6e109897f4d866eb1a3d31cbb2220c0b5e3dc74704208189ecc3bec787740e5f`.
  이는 로컬에서 측정한 identity이며 publisher가 제공한 checksum 검증이라고 주장하지 않는다.
- 최초 `openslr.trmal.net`에서 받은 부분을 `openslr.elda.org`에서 range 재개했다.
  전환 전 같은 1 MiB range의 SHA-256 일치를 확인했고 최종 전체 archive를 읽었다.
- 부속 LM/lexicon은 선택 추출에서 제외했다. 모든 member의 traversal/link/type 검사는 유지했다.
- 실제 train FLAC 22,263개를 전부 디코드했다. 모두 16 kHz, mono, PCM 16-bit이며
  decoded frame count와 metadata가 일치했다. Byte-unique 22,263개, 2,813,430,983 bytes다.
- 총 길이 186,036,486 ms = **51.676802시간**. 최소/최대 3,303/20,665 ms,
  30초 초과 파일은 0개다. 아직 accepted hours에 포함하지 않는다.
- 화자 ID는 경로의 script ID와 분리했고 train/test 화자 교집합 없음 검사를 통과했다.
  개인 이름은 canonical sample metadata에 옮기지 않는다.
- Clipping 비율 최대 875 ppm, 저진폭 sample 비율 최대 623,984 ppm이다.
  이는 waveform 측정값일 뿐 noise/SNR label이나 human 품질 판정이 아니다.
  녹음 환경·잡음 종류는 아직 미확인으로 남긴다.

## 처리 및 미완료 게이트

- 처리 코드 `2efb3ed2519a2d5db91cec5ba8ec227581268162`로 inventory를 생성했다.
- Whisper large-v3-turbo의 pinned weight/config와 Korean MFA 3.0.0의 acoustic/dictionary
  SHA-256을 실제 파일에서 재검증했다. 추가 모델 다운로드나 새 runtime 설치는 하지 않았다.
- 실제 FLAC 1개 MFA 사전 검증은 word 44개, phone 166개를 반환했다.
  전체 105명/22,263개 batch MFA는 진행 중이며 Whisper baseline은 그 다음 단계다.
- 최종 bundle에는 bounded word/phone 원문 구간을 보존하고 canonical importer에서
  counts/coverage를 재계산한다. Manifest와 bundle을 각각 immutable object로 보존한다.
- 공식 test 전사와 중복되는 normalized train 전사, byte duplicate, ASR/정렬 실패는
  최종 반입 대상에서 제외한다. 제외 수량과 accepted duration은 아직 확정하지 않는다.
- Source quality evidence, source review, canonical hash import, object/split 검증,
  새 snapshot은 미완료다. 기존 `alpha10` snapshot을 수정하지 않는다.
- 현재 Korean STT accepted **0시간**, target speech effective **0시간**이다.
  Korean STT 100시간과 TTS 30시간 release gate는 계속 미충족이다.

## 검증

- `make validate`: offline 14 checks, root 23 tests PASS.
- Foundry 33 tests PASS. 새 회귀 검사는 archive 선택/경로 탈출, MFA PATH,
  ASR CER 변조, 정렬 구간 범위, 재수입 manifest 변조와 STT/TTS 시간 분리를 보호한다.
- Raw archive/FLAC, inventory, 모델 결과, SQLite는 Git 밖에만 보존한다.
