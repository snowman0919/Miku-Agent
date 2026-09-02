# Persona Corpus

Persona sample은 constitution의 12 dimension과 hard violation을 별도 저장한다. Hard constraint를 먼저 적용하고 cosine similarity가 0 이하면 reject한다. 양수는 자동 승인이 아니다. Fidelity, utility, naturalness, Korean fluency, relationship, agentic correctness와 novelty를 분리 평가한다.

Source observation과 training conversation을 구분한다. Synthetic generation은 generator/revision/template/seed/critic/adjudication provenance가 필요하다. 현재 deterministic pilot은 pipeline 규모와 schema 검증용 quarantine이며 Gold/Silver나 human-reviewed data가 아니다.
