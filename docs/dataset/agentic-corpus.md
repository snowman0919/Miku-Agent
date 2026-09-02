# Agentic Corpus

Trajectory는 user request, tool selection/call, result, verification과 정직한 Miku-style report를 보존한다. Memory, Codex delegation, repository/file, research, scheduler, permission, cancellation과 retry/rollback 유형을 분리한다. Failure/recovery sample을 성공 sample과 함께 유지한다.

Execution-backed 표시는 실제 격리 실행 receipt가 있을 때만 사용한다. Synthetic tool result는 provenance로 명시하며 host Docker socket, privileged mode, secret, 실제 external write를 주지 않는다. 현재 pilot은 `execution_backed=false`다.
