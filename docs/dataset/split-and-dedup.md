# Split, Holdout and Deduplication

Split key는 sample ID가 아니라 source work, derivative family, speaker/render session, script template family와 lineage root다. `SHA256(policy_version + NUL + group_id)`의 고정 integer threshold로 결정해 insertion order와 Python hash seed에 독립적이다.

Frozen eval group은 일반 hash assignment보다 우선하며 training export에 들어가지 않는다. Exact SHA-256, acoustic/text near duplicate와 lineage duplicate가 뒤늦게 서로 다른 split을 연결하면 자동 이동하지 않고 leakage conflict로 sealing/export를 차단한다.
