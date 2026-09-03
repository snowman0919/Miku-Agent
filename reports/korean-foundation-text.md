# Korean Foundation Text Intake

## Result

- Source: Korean Wikipedia `pages-articles`, 2026-09-01 dated dump.
- Accepted: 78,112 documents, 129,341,916 pinned-tokenizer tokens.
- Training export: 78,112 rows, SHA-256 `4f31bd44fa8180d206d30ba1e40c97da710bedf4e74af1b29c4e18525447fa0e`.
- Semantic effective unique: 78,082 at cosine 0.98; 78,110 at cosine 0.99.
- Lexical effective unique: 78,112 at normalized exact and Jaccard 0.8 character/token checks.
- Korean foundation text gate: PASS. Korean STT 100시간 gate는 BLOCKED다.

## Source and Rights

- Official URL: `https://dumps.wikimedia.org/kowiki/20260901/kowiki-20260901-pages-articles.xml.bz2`
- Dump bytes: 1,365,272,177.
- Dump SHA-1: `a1cfa0e29bdbb802b42e1f5891bd883664da8577`.
- Dump SHA-256: `d6c8bf7a1462c61e03ae52e0babc8d52677226287a69b9e7eefbbb047a9f24b8`.
- License: CC BY-SA; attribution과 share-alike가 필요하다.
- Scope: private internal training only. 별도 compliance 검토 전에는 corpus, model, adapter 또는 파생물을 공개 배포하지 않는다.
- Latest rights evidence manifest SHA-256: `da0c7d1151562f0776d8d5512f65ab5c15b2c125b7b2e4f5d87e751fdf6fe8e0`.

## Processing and Quality

- Processor revision: `e83b5aa01bf89a291751abdba8bbef21ed403706`.
- Policy SHA-256: `6bd86ada59f17ce91d691fb09645d0827578e72b77ae8e8e6af9776fd7005196`.
- Tokenizer: `nvidia/NVIDIA-Nemotron-Nano-9B-v2@6533e8de2c68e4536bf7c411d7a3ce5734111476`.
- Tokenizer files SHA-256: `3277c00fe5fb3963b3cb7c07b7f183722d2af4d775a4aea7cfb3684d7cccbc2f`.
- Scanned prefix: 150,000 pages; redirects 52,547, short/non-Korean 14,220, cleaning-empty 5,121을 제외했다.
- Removed: boilerplate sentences 130, PII-like sentences 1,582, exact duplicate sentences 128,571, near-duplicate sentences 3,302.
- Independent full-row verification: 78,112 rows와 129,341,916 tokens를 재계산했고 sample/document identity, provenance, policy, processor, dump, tokenizer, hash, quality, token count, URL, PII 13개 검사 결과는 모두 0이다.
- Quality receipt SHA-256: `835c8ed821ace49e29f5044f49d68948091b94d7f5aadad1bd65bbe5c2f1e96f`.
- Lexical duplicate report SHA-256: `ac853ffb8e712422490649b112776dadc7051720ceb0e77c5043a181ec98d77b`; character/token candidate pairs 1,213/609에서 verified match는 모두 0이다.
- Semantic duplicate report SHA-256: `87c6ae8ce6f63b728017ac408df7ab544f29829a5fe58543c1b7ea8727a0ac50`.

첫 150,000-page 처리본에서 실제 `섬네일|...`/`파일:...` 문장 94개가 발견되어 승격하지 않았다.
문장 단위 제거를 공통 cleaner에 추가한 뒤 전체를 다시 처리하고 독립 검사를 통과한 결과만 accepted로 수입했다.
거부본은 worker의 Git 밖 경로에 보존했다.

## Artifacts

- Clean bundle: 188,048,130 bytes, SHA-256 `7c03d5e4dc6353cf83c772fb1f3e732dbb52a0c9ceb954034876d11d5d561cb3`.
- Bundle manifest SHA-256: `614d4689cca5f21ac70e35307c3a21edbd1c5ee591c1fb49c0fbc85aada35b7b`.
- Canonical source ID: `d45dc524-fc48-574a-8e59-5b4fd3e9aee7`.
- Review ID: `209e6d1f-a614-4345-a0d0-d02440eedc85`.
- Import dry-run, actual import, repeated idempotent import를 모두 실행했다.

## Limitations

- 전체 dump가 아니라 결정론적 150,000-page prefix다.
- 자동화된 URL/PII/boilerplate 휴리스틱과 20개 결정론적 발췌 검토는 완전한 법률·개인정보·내용 검토를 대신하지 않는다.
- Semantic 모델의 최대 입력 길이는 512 tokens이므로 긴 문서의 의미 중복 평가는 잘린 표현을 사용한다.
- 이 corpus는 Korean STT 100시간, target speech, persona, Agentic, Duplex 및 human calibration gate를 충족하지 않는다.
