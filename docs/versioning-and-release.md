# Versioning and Release

Semantic version을 사용한다. Definition/schema 호환 변경은 patch, backward-compatible capability는 minor, protocol·memory meaning을 깨는 변경은 major 후보로 평가한다. Accepted decision 변경은 새 ADR이 기존 ADR을 supersede하고 product lock, schema, docs, tests, traceability를 같은 release에서 갱신해야 한다.

Release는 local validation, report, document hash, source commit, private visibility, clean tree를 증거로 남긴다. Tag는 annotated `vX.Y.Z`를 사용한다. V0.0.0에는 public GitHub release와 package publication을 만들지 않는다.

