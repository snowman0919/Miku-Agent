# Open Questions

이 문서는 accepted 결정을 다시 여는 목록이 아니라 후속 구현 실험으로만 답할 수 있는 선택을 관리한다.

| Question | Why it matters | Available options | Decision criteria | Required experiment | Target decision version |
|---|---|---|---|---|---|
| Backend 언어/framework는 무엇인가 | concurrency, schema tooling, hiring/maintenance | Python/FastAPI, Kotlin, Go, Rust | streaming latency, library fit, operability | 동일 WS/auth skeleton benchmark | V0.7.0 |
| Vector DB vendor는 무엇인가 | retrieval quality와 운영 복잡성 | pgvector, Qdrant, Milvus 계열 | filtered recall, backup, cost | namespace-filtered corpus benchmark | V0.7.0 |
| Graph DB vendor는 무엇인가 | 관계 projection 운용 | Neo4j, Memgraph, document projection | query need, consistency, ops cost | representative relationship queries | V0.7.0 |
| Flutter Clerk integration 방식은 무엇인가 | 보안과 유지보수 | community SDK, native SDK platform channel | support, token lifecycle, platform parity | sign-in/revoke spike | V0.8.1 |
| Flutter/Unity character surface 통합 방식은 무엇인가 | 성능·개발 복잡성 | Flutter renderer, embedded Unity, native bridge | RAM, FPS, startup, VRM feature | 동일 asset prototype | V0.8.1 |
| 모바일 local 2~4B foundation model은 무엇인가 | offline/reflex 품질 | 후보군 benchmark 후 결정 | device support, Korean, multimodal, license | target devices offline suite | V0.8.1 |
| 모바일 quantization format은 무엇인가 | footprint와 latency | INT4/INT8 및 backend formats | quality, thermal, ONNX compatibility | device matrix | V0.8.1 |
| Audio codec/packet duration은 무엇인가 | latency·bandwidth·품질 | PCM16, low-delay Opus; multiple packet sizes | TTFA, interruption, loss, CER | controlled network benchmark | V0.1.0 |
| Full LLM training hardware는 무엇인가 | 11B full tuning feasibility | rented multi-GPU options | memory, throughput, cost, availability | adapter evidence 후 capacity plan | V0.3.x |
| 정확한 음성 source registry는 무엇인가 | 품질과 권리 | owned/licensed/permitted sources | rights, speech-likeness, coverage | source-by-source review | V0.2.0 |
| 실제 Clerk production plan은 무엇인가 | Allowlist 기능·비용 | eligible Clerk plans | exact allowlist, cost, limits | current plan review | V0.7.0 |
| Push provider 세부 구현은 무엇인가 | 모바일 delivery | FCM/APNs adapter options | reliability, privacy, Flutter support | minimal delivery spike | V0.8.0 |
| Cloudflare 경유 방식은 무엇인가 | edge/auth/WS topology | direct origin, proxy, tunnel/product mix | WS behavior, trust boundary, cost | reconnect/auth benchmark | V0.7.0 |

