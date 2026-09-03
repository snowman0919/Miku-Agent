# Duplex Corpus

- Infrastructure fixture 500, frozen evaluation 500, accepted 2,000.
- Human adjudicated accepted 0, audio/timestamp-backed accepted 2,000.
- Accepted synthetic timestamp corpus는 distinct event sequence 2,000, scenario 12개(각 166~167),
  event count 4/5/6개, template family 192개이며 최대 family는 11행이다.
- Overlap timeline 167개, explicit silence timeline 333개다. Audio reference와 human 판정을 넣지 않았다.
- Generator SHA-256 `1930c1eee61dc71a9db632bfda4e794fd509ab84a6b7a771b5a886ffa8d09154`,
  bundle SHA-256 `b31e0eeda09d413d63dd4bce84ce8e3b1862c341564684544ea48a613749e2e7`,
  accepted export SHA-256 `2e7bf3327be5f3c56ab20157e78c62d65cd7df81325d2b3125ccecad4d548eb5`다.
- Evaluation 500개에는 synthetic timestamp/event evidence가 있으나 audio와 human adjudication은 없다.
- Fixture와 evaluation을 actual full-duplex 또는 release corpus 성능으로 계산하지 않는다.

Release minimum 대비 accepted 8,000, human adjudicated 1,000이 부족하다. Audio/timestamp-backed 2,000 최소값은 충족했다.
