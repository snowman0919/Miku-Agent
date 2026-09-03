# GPU Worker Model Selection

## 상태

실제 RTX 5090에서 immutable revision과 weight/config hash를 확인하고 허용된 합성
fixture로 후보를 비교했다. 선택은 V0.2.0 pilot의 잠정 default이며 실제 Miku/human/
singing data calibration 전에는 품질 임계값으로 사용하지 않는다. 전체 binding은
`experiments/v0.2.0-gpu-worker/model-registry.json`에 있다.

## RTX 5090에서 필요한 비교

| Task | Candidate | Pilot result | Decision |
|---|---|---|---|
| source separation | htdemucs / Open-Unmix umxhq | 단일 비교에서 vocal SI-SDR 22.78 / 17.85 dB; htdemucs 10개 vocal 평균 21.98 dB | htdemucs 잠정 default, umxhq fallback |
| ASR | Whisper large-v3-turbo / MMS-1B-all | 50개 합성 한국어 CER 0.3529 / 0.5625, RTF 0.01129 / 0.00313 | Whisper 잠정 default; MMS는 NC license와 낮은 품질로 reject |
| forced alignment | Korean MFA 3.0.0 / MMS CTC | canonical STT eval 합성음 20개에서 MFA beam 100은 실패 0, word 280/phone 1,067 interval, end-to-end RTF 0.3000; 기본 beam은 4개 누락 | CC BY 4.0 MFA를 attribution-required default로 선택; CC-BY-NC MMS는 blocked 유지 |
| speaker embedding | SpeechBrain ECAPA / X-vector | 50개 단일화자 centroid 평균 0.9301 / 0.9921, RTF 0.00320 / 0.00357 | X-vector 잠정 default, ECAPA fallback; threshold 미보정 |
| audio quality | PCM16 reference components | 50개 protocol pilot | `NOT CALIBRATED`, canonical score 아님 |
| prosody | PCM16 autocorrelation/energy | 50개 protocol pilot | raw F0/energy/voicing 보존, `NOT CALIBRATED` |
| audio embedding / critic / generator | 미실행 | optional gate | `UNRESOLVED` |

모든 candidate record는 immutable revision, weight/config SHA-256, weight/code license,
commercial/redistribution/output restriction, dtype, environment와 measured peak VRAM을
포함한다. `main` 또는 `latest`만 기록한 profile은 runtime에서 거부한다. ASR의 실제
human/Miku/singing/일본어/code-switch 품질과 speaker threshold는 후속 calibration 대상이다.
MFA 결과도 자동 acceptance가 아니며 이름·외래어의 `spn` 5개와 실제 target voice 경계를
사람이 검수해야 한다. 상세 수치와 lock은 `reports/mfa-korean-alignment-benchmark.json`에 있다.
