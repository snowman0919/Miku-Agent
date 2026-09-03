# Duplex Corpus

- Infrastructure fixture 500, frozen evaluation 500, accepted 2,000.
- Human adjudicated accepted 0, audio/timestamp-backed accepted 2,000.
- Accepted synthetic timestamp corpus는 distinct event sequence 2,000, scenario 12개(각 166~167),
  event count 4/5/6개, template family 192개이며 최대 family는 11행이다.
- Normalized text unique는 1,955개, 0.8 Jaccard character/token effective unique는
  1,877/1,939개다. Pinned multilingual E5 cosine 0.98/0.99 semantic effective unique는
  582/1,453개이고 최대 semantic cluster는 168/47행이다.
- Overlap timeline 167개, explicit silence timeline 333개다. Audio reference와 human 판정을 넣지 않았다.
- Generator SHA-256 `1930c1eee61dc71a9db632bfda4e794fd509ab84a6b7a771b5a886ffa8d09154`,
  bundle SHA-256 `b31e0eeda09d413d63dd4bce84ce8e3b1862c341564684544ea48a613749e2e7`,
  accepted export SHA-256 `2e7bf3327be5f3c56ab20157e78c62d65cd7df81325d2b3125ccecad4d548eb5`다.
- Evaluation 500개에는 synthetic timestamp/event evidence가 있으나 audio와 human adjudication은 없다.
- Fixture와 evaluation을 actual full-duplex 또는 release corpus 성능으로 계산하지 않는다.

Release minimum은 effective unique 기준이다. Primary cosine 0.98 기준 accepted와
audio/timestamp-backed가 각각 9,418/1,418개, human adjudicated가 1,000개 부족하다.
Raw audio/timestamp-backed row 2,000개만 충족했으며 이를 effective minimum 충족으로 표시하지 않는다.
