# Agentic Corpus Pilot

- Trajectories: 500; 각 task type 100 (`file.read`, `repository.inspect`, `permission.request`, `result.verify`, `tool.failure`).
- Failure/recovery candidates: 100.
- Execution-backed: 0.
- Synthetic verified-success flag: 400; actual execution-backed completion: 0.
- Training status: quarantine 500.

실제 isolated task receipt가 없으므로 synthetic `verified` field를 execution evidence로 보고하지 않는다.
