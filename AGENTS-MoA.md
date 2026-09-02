# Agent Working Agreement

이 문서는 Miku Agent repository에서 작업하는 parent agent와 subordinate agent가 따라야 하는 공통 실행 계약이다.

모든 agent는 작업을 시작하기 전에 이 문서를 읽고, 현재 checkout의 `spec/product-lock.yaml`, accepted ADR, release source binding을 확인해야 한다.

---

# 1. Source of Truth

충돌 시 우선순위는 다음과 같다.

1. `spec/product-lock.yaml`
2. accepted ADR
3. 현재 release의 `release-manifest.yaml`
4. `docs/product-charter.md`
5. JSON Schema
6. `docs/roadmap.md`
7. component README
8. 현재 task/goal의 명시적 사용자 결정
9. subordinate agent의 제안

Subordinate agent의 출력은 source of truth가 아니다.

기존 accepted 결정을 변경하려면 기존 ADR을 조용히 수정하지 않고 superseding ADR이 필요하다.

---

# 2. Parent Agent

Miku Agent engineering workflow의 유일한 parent orchestrator는 Codex다.

```text
User
 |
 v
Codex Parent
 |
 +-- Command Code workers
 |
 +-- OpenCode workers
 |
 +-- deterministic tools/tests
 |
 +-- RTX 3080 / RTX 5090 workers
```

Codex Parent가 담당한다.

```text
requirement interpretation
task decomposition
agent role assignment
context construction
permission assignment
worktree assignment
subagent dispatch
result collection
evidence validation
cross-agent comparison
conflict resolution
merge decision
release decision
user-facing final report
```

Subordinate agent는 parent 역할을 승계하지 않는다.

Subordinate agent가 다른 subordinate agent를 임의로 생성하거나 전체 orchestration policy를 변경해서는 안 된다.

---

# 3. Subordinate Agent Providers

현재 두 provider를 사용한다.

```text
Command Code
OpenCode
```

Credential은 repository root 또는 실행 환경의 `.env`에서 다음 이름으로 제공된다.

```text
COMMANDCODE_API_KEY=
OPENCODE_API_KEY=
```

실제 값은 절대로 이 문서, Git, log, prompt, report, test fixture에 기록하지 않는다.

`.env`는 반드시 Git ignore 대상이어야 한다.

Agent는 다음을 하지 않는다.

```text
API key 출력
API key 일부 출력
environment 전체 dump
.env 내용 출력
credential을 subprocess command argument에 평문 삽입
credential을 result JSON에 기록
credential을 generated code에 삽입
credential을 Git에 commit
credential을 subordinate prompt에 포함
```

필요한 runtime adapter만 environment에서 credential을 읽는다.

Credential 존재 여부는 다음처럼 boolean 상태로만 취급한다.

```text
available
missing
invalid
```

값 자체를 노출하지 않는다.

---

# 4. Provider Weight

기본 provider weight는 다음으로 고정한다.

```yaml
provider_weights:
  command_code: 2
  opencode: 1
```

즉 기본 장기 목표 utilization은:

$$
CommandCode : OpenCode = 2 : 1
$$

이다.

정상적인 eligible workload에서 목표 share는 대략:

```text
Command Code: 66.7%
OpenCode:     33.3%
```

이다.

이 비율은 provider 사용량과 실행 기회를 분산하기 위한 기본 scheduling policy다.

---

# 5. 2:1 비율의 의미

2:1을 다음처럼 구현하지 않는다.

```text
작업 1 -> Command Code
작업 2 -> Command Code
작업 3 -> OpenCode
무조건 반복
```

작업 적합성을 무시한 고정 round-robin은 금지한다.

대신 다음 순서로 routing한다.

```text
Task
 |
 v
Capability / Permission Eligibility
 |
 v
Candidate Providers
 |
 v
Role Suitability
 |
 v
Weighted Fair Scheduler
Command Code weight=2
OpenCode weight=1
 |
 v
Selected Worker
```

즉 provider가 해당 역할에 적합한 경우에만 2:1 weight가 적용된다.

---

# 6. Weighted Fair Scheduling

Parent는 최근 실행 이력을 기준으로 provider share를 유지한다.

권장 scoring:

$$
S_p =
\frac{W_p}{1 + U_p}
$$

여기서:

```text
W_p = provider weight
U_p = 최근 scheduling window에서 해당 provider가 소비한 normalized usage
```

기본:

```text
W_command = 2
W_opencode = 1
```

또는 동등한 weighted deficit round-robin 구현을 사용할 수 있다.

중요한 것은 정확한 algorithm 이름이 아니라 다음 invariant다.

```text
장기적인 eligible workload에서 Command Code가 OpenCode의 약 2배 비중
```

을 가져야 한다.

---

# 7. Scheduling Window

비율을 단일 작업 수준에서 강제하지 않는다.

다음 중 구현에 적합한 하나를 사용한다.

```text
최근 30 subordinate jobs
최근 100 normalized work units
최근 24시간의 eligible workload
```

초기 권장 기준:

```yaml
scheduling_window:
  type: completed_jobs
  size: 30
```

단 단순 job count가 실제 사용량을 심하게 왜곡한다면 normalized usage 기반으로 전환한다.

변경은 measurement evidence와 함께 기록한다.

---

# 8. Normalized Usage

가능하면 단순 요청 수보다 다음을 고려한다.

```text
wall time
input tokens
output tokens
provider reported usage
cost
number of agent turns
task complexity
```

초기 구현에서 모든 provider가 동일한 usage metadata를 제공하지 않는다면:

```text
completed job = 1 work unit
```

으로 시작해도 된다.

단 향후 telemetry가 쌓이면 normalized usage로 전환한다.

---

# 9. Hard Routing Overrides

2:1 provider weight보다 다음 조건이 항상 우선한다.

## Capability

특정 provider/runtime에서만 가능한 기능이 필요한 경우 해당 provider를 사용한다.

## Reliability

최근 동일 task class에서 반복 실패한 provider는 일시적으로 routing 대상에서 제외할 수 있다.

## Permission

필요한 permission profile을 안전하게 제공할 수 없는 provider에는 작업을 보내지 않는다.

## Reproducibility

benchmark, release audit, deterministic comparison에서는 provider를 명시적으로 고정할 수 있다.

## User instruction

사용자가 provider 또는 model을 명시하면 그 요청이 우선한다.

## Provider unavailable

API quota, authentication, outage 등의 이유로 provider가 unavailable이면 다른 provider로 failover할 수 있다.

이때 2:1 비율을 맞추기 위해 작업을 의도적으로 지연하지 않는다.

---

# 10. Default Functional Roles

여러 모델을 단순 다수결 ensemble로 사용하지 않는다.

Subordinate agents는 서로 다른 기능적 역할을 갖는다.

기본 역할:

```text
SCOUT
ARCHITECT
IMPLEMENTER
CRITIC
SECURITY_REVIEWER
DATA_REVIEWER
TEST_DESIGNER
DEBUGGER
BENCHMARK_ANALYST
```

---

# 11. Command Code 기본 역할

Command Code는 기본적으로 실행과 구현 비중을 높게 둔다.

우선 역할:

```text
IMPLEMENTER
DEBUGGER
REFACTORER
REPOSITORY_WORKER
TEST_EXECUTOR
EXECUTION_REVIEWER
```

특히 다음과 같은 작업에 우선 고려한다.

```text
repository modification
multi-file implementation
refactoring
build failure resolution
test execution
concrete bug fix
working-tree manipulation
implementation-backed investigation
```

Command Code가 항상 더 좋은 모델이라고 가정하지 않는다.

실제 task telemetry와 benchmark에 따라 routing preference는 조정할 수 있다.

Provider base weight `2`는 유지하되 role-specific multiplier를 사용할 수 있다.

예:

```yaml
command_code:
  base_weight: 2
  role_multipliers:
    implementer: 1.5
    debugger: 1.3
    critic: 0.8
```

---

# 12. OpenCode 기본 역할

OpenCode는 기본적으로 독립적인 탐색과 비판 역할 비중을 높게 둔다.

우선 역할:

```text
SCOUT
CRITIC
ARCHITECTURE_CRITIC
DATA_REVIEWER
SECURITY_REVIEWER
ALTERNATIVE_DESIGNER
```

특히 다음 작업에 우선 고려한다.

```text
independent alternative
design critique
counterexample search
schema review
architecture review
failure hypothesis
data quality review
read-only investigation
```

예:

```yaml
opencode:
  base_weight: 1
  role_multipliers:
    critic: 1.5
    scout: 1.4
    implementer: 0.8
```

Role multiplier는 provider 기본 사용량 목표를 보조할 뿐 장기간 Command Code 2 : OpenCode 1이라는 전체 목표를 무시하지 않는다.

---

# 13. Model Selection

Parent는 가능하면 provider 내부의 정확한 model을 명시한다.

다음 형태를 권장한다.

```text
role
-> provider
-> model
```

모델명이 orchestration의 stable API가 되어서는 안 된다.

Stable interface는 role이다.

예:

```yaml
role: implementation

provider: command_code
model: auto_or_explicit
```

향후 모델 변경은 parent workflow를 깨지 않아야 한다.

---

# 14. Model Router Telemetry

모든 subordinate 실행에 다음 metadata를 기록한다.

```yaml
job_id:
parent_task_id:

role:

provider:
model:

repository:
base_commit:
result_commit:

task_class:
language:
domain:
complexity:

permissions:

timing:
started_at:
completed_at:
wall_ms:

usage:
input_tokens:
output_tokens:
provider_units:
estimated_cost:

result:
status:
tests_passed:
review_score:
rework_required:

failure:
category:
reason:
```

지원하지 않는 usage 값은 `null`로 기록한다.

추측해서 채우지 않는다.

---

# 15. Adaptive Routing

충분한 데이터가 쌓이면 모델과 provider를 다음 utility로 평가할 수 있다.

$$
Utility(m,t)=
Q(m,t)
-\lambda C(m,t)
-\mu L(m,t)
-\nu R(m,t)
$$

여기서:

```text
Q = quality / task success
C = cost
L = latency
R = rework or failure risk
```

다만 adaptive router는 provider의 기본 2:1 budget policy와 함께 동작한다.

즉:

```text
quality routing
+
budget weighting
```

을 결합한다.

---

# 16. Worktree Isolation

두 coding agent가 동일한 writable working tree를 동시에 사용하지 않는다.

Writable subordinate job은 가능한 한 독립 Git worktree를 사용한다.

예:

```text
.worktrees/
  cmd-<job-id>/
  oc-<job-id>/
```

각 worker:

```text
same base commit
isolated working tree
isolated branch
```

를 가진다.

Subordinate branch 예:

```text
agent/cmd/<job-id>
agent/oc/<job-id>
```

Worker가 parent branch에 직접 commit하지 않는다.

---

# 17. Read-only Roles

다음 역할은 기본적으로 read-only다.

```text
SCOUT
CRITIC
SECURITY_REVIEWER
DATA_REVIEWER
ARCHITECTURE_CRITIC
```

Permission:

```text
filesystem: read-only
git: read-only
shell: safe-read commands only
network: task-dependent
```

Review agent가 코드를 고치고 자신의 수정안을 다시 승인하는 구조를 피한다.

---

# 18. Writable Roles

다음은 write permission을 가질 수 있다.

```text
IMPLEMENTER
DEBUGGER
REFACTORER
```

단:

```text
isolated worktree
allowed repository root
no unrelated path
no host-wide configuration
```

을 지킨다.

---

# 19. Shell Permission

Subordinate agent에게 unrestricted host shell을 기본 제공하지 않는다.

가능하면 permission profile을 사용한다.

```yaml
reviewer:
  filesystem: read-only
  shell: read-only
  network: deny

implementer:
  filesystem: worktree-write
  shell: project-scoped
  network: conditional

benchmark:
  filesystem: experiment-write
  shell: experiment-scoped
  network: conditional
```

`--yolo` 또는 이에 준하는 unrestricted mode는 기본값으로 사용하지 않는다.

필요한 경우 parent가 isolated environment임을 확인하고 명시적으로 승인한다.

---

# 20. SubAgent Job Contract

모든 subordinate agent 작업은 가능한 한 구조화된 job spec으로 생성한다.

예:

```yaml
job_id: "<uuid>"

role: "critic"

goal: >
  Review the dataset lineage split implementation and identify
  cases where derived samples can cross train/eval boundaries.

repository:
  name: Miku-Agent
  base_commit: "<sha>"
  worktree: null

constraints:
  - Do not modify files.
  - Do not redesign accepted product decisions.
  - Every finding must include concrete evidence.
  - Do not create low-signal tests.

permissions:
  filesystem: read-only
  shell: read-only
  network: deny

budget:
  timeout_seconds: 900
  max_turns: 20

expected_output:
  schema: subagent-review-v1
```

---

# 21. Structured Result Contract

자유형 자연어만 결과로 받는 것을 지양한다.

Reviewer output 예:

```json
{
  "status": "issues_found",
  "summary": "...",

  "findings": [
    {
      "severity": "high",
      "category": "data-leakage",
      "file": "services/dataset-foundry/src/...",
      "line": 123,
      "claim": "...",
      "evidence": "...",
      "failure_mode": "...",
      "suggested_fix": "..."
    }
  ],

  "confidence": 0.91
}
```

Implementer output 예:

```json
{
  "status": "completed",

  "base_commit": "...",
  "result_commit": "...",

  "changed_files": [],

  "validation": [
    {
      "command": "...",
      "exit_code": 0,
      "result": "PASS"
    }
  ],

  "known_failures": [],
  "notes": []
}
```

---

# 22. Evidence Hierarchy

Parent는 subordinate agent의 자신감이나 다수결보다 실제 evidence를 우선한다.

우선순위:

$$
Executable\ Evidence
>
Source\ Evidence
>
Independent\ Review
>
Model\ Assertion
>
Model\ Confidence
$$

예:

```text
Command Code PASS
OpenCode PASS
actual integration test FAIL
```

이면 결과는 FAIL이다.

세 agent가 같은 주장을 했다는 이유만으로 사실로 승격하지 않는다.

---

# 23. Functional Ensemble

같은 질문을 여러 모델에 보내 단순 투표하는 것을 기본 전략으로 사용하지 않는다.

우선:

```text
Agent A -> design
Agent B -> counterexample
Agent C -> implementation
Agent D -> verification
```

처럼 역할을 직교화한다.

동일 작업을 여러 agent에게 중복시키는 것은 다음 경우에만 허용한다.

```text
high-risk design decision
model/provider benchmark
disputed review
security-sensitive change
high-value architecture branch
```

중복 실행 이유를 metadata에 기록한다.

---

# 24. Parent Adjudication

Subordinate 결과가 충돌하면 Codex Parent가 다음을 수행한다.

```text
1. claims 분리
2. evidence 확인
3. 실제 code/source 확인
4. 필요한 test 실행
5. 필요한 경우 제3의 critic dispatch
6. 결정
```

단순 provider reputation으로 승자를 고르지 않는다.

---

# 25. Merge Policy

Subordinate agent의 commit을 바로 merge하지 않는다.

Parent는 최소 다음을 확인한다.

```text
base commit
diff
scope
tests
architecture invariants
secret scan
forbidden files
review findings
```

필요한 경우 worker commit 전체를 merge하지 않고 selected patch만 가져올 수 있다.

Parent가 최종 integration commit을 만든다.

---

# 26. Test Policy

모든 agent는 repository의 기존 테스트 철학을 따른다.

테스트는 최소 하나를 보호해야 한다.

```text
real user requirement
known/plausible failure mode
architectural invariant
numerical correctness
data integrity
real integration
optimization connectivity
reproducibility
deployment correctness
measurable output quality
```

다음을 위한 테스트는 금지한다.

```text
pass count 증가
coverage 증가 자체
getter 확인
constant 확인
hard-coded mapping 재확인
파일 존재만 확인
shape만 확인
trusted library가 이미 보장하는 trivial behavior
```

테스트를 작성하기 전에:

```text
어떤 결함, 회귀, 요구, 결정을 보호하는가
```

를 설명할 수 있어야 한다.

---

# 27. Provider Failure

Provider 실행 실패는 다음 taxonomy로 분류한다.

```text
AUTH_MISSING
AUTH_INVALID
QUOTA_EXCEEDED
PROVIDER_UNAVAILABLE
MODEL_UNAVAILABLE
TIMEOUT
AGENT_RUNTIME_ERROR
OUTPUT_SCHEMA_INVALID
TOOL_FAILURE
WORKTREE_FAILURE
TASK_FAILURE
UNKNOWN
```

Provider 실패와 task 자체의 실패를 구분한다.

---

# 28. Failover

Provider가 unavailable하면 다른 provider로 failover할 수 있다.

예:

```text
Command Code quota exhausted
-> OpenCode eligible
-> OpenCode로 dispatch
```

이 결과로 일시적으로 2:1 비율이 깨지는 것은 허용한다.

Provider가 다시 사용 가능해졌다고 해서 과거 비율을 맞추기 위해 의미 없는 작업을 생성하지 않는다.

---

# 29. Rework Accounting

Subordinate 결과가 parent 또는 critic에 의해 거부되고 재작업이 필요하면 기록한다.

```text
rework_required: true
rework_reason:
```

Provider 성능 평가에는 최초 성공률뿐 아니라:

```text
rework rate
review defect rate
test failure rate
```

를 포함한다.

---

# 30. Initial Orchestration Pilot

초기에는 agent pool을 과도하게 확장하지 않는다.

최소 구성:

```text
PARENT
Codex

IMPLEMENTER
Command Code

SECONDARY IMPLEMENTER / DEBUGGER
Command Code

SCOUT / CRITIC
OpenCode
```

논리적으로:

```text
Command Code role capacity: 2
OpenCode role capacity: 1
```

이라는 기본 형태다.

---

# 31. Initial 2:1 Pilot

첫 평가 구간은 실제 engineering task 최소 30개를 권장한다.

가능하면:

```text
Command Code eligible dispatch 약 20
OpenCode eligible dispatch 약 10
```

을 목표로 한다.

단 capability routing 때문에 정확히 20/10일 필요는 없다.

측정:

```text
task success
test pass
review score
rework
latency
usage
cost
defects discovered
```

이 pilot 결과로 role multiplier를 조정할 수 있다.

Provider base weight 자체를 변경하려면 사용자 결정이 필요하다.

---

# 32. Dataset Foundry Role Examples

현재 V0.2.0에서는 다음과 같이 사용하는 것을 권장한다.

## Command Code

```text
object store implementation
SQLite transaction implementation
job runner
audio worker implementation
review UI
migration
bug fixing
integration tests
```

## OpenCode

```text
data leakage critique
rights schema critique
transformation DAG review
audio pipeline alternatives
persona dataset critique
security review
counterexample generation
```

---

# 33. RTX 5090 GPU Worker Role Examples

## Command Code

```text
GPU worker implementation
batch scheduler
ASR adapter implementation
separation adapter
error recovery
benchmark harness
```

## OpenCode

```text
model candidate comparison
quality metric critique
GPU worker protocol review
failure analysis
benchmark interpretation
```

---

# 34. Environment Loading

Runtime wrapper만 `.env`를 읽는다.

권장 형태:

```text
scripts/subagents/
  run-command-code
  run-opencode
```

Wrapper가:

```text
.env load
required key existence check
provider invocation
structured output capture
secret redaction
```

을 담당한다.

Parent prompt 자체에 API key를 삽입하지 않는다.

---

# 35. Secret Redaction

Subagent stdout/stderr는 저장 전에 secret scanner를 거친다.

최소 다음을 redact한다.

```text
COMMANDCODE_API_KEY value
OPENCODE_API_KEY value
Bearer token
Authorization header
common API key pattern
```

API key가 output에 발견되면:

```text
job status = SECURITY_FAILURE
```

로 처리하고 해당 raw log를 canonical artifact로 저장하지 않는다.

---

# 36. Repository Safety

다음을 commit하지 않는다.

```text
.env
subagent credential
provider cache
provider session state
agent transcript containing secrets
large raw agent logs
temporary worktree
```

가능한 metadata만 저장한다.

```text
job spec
provider/model
usage metrics
result schema
result commit
validation
```

---

# 37. Hidden Adaptive State

Automated benchmark worker에서는 provider가 사용자 취향을 비공개 상태로 누적하는 기능이 있다면 비활성화하는 것을 원칙으로 한다.

이유:

```text
reproducibility
A/B comparison
hidden-state contamination
cross-task leakage
```

Interactive human-driven session과 automated worker를 분리한다.

자동 worker는 가능한 한 stateless 실행을 사용한다.

---

# 38. Auto Update

Automated subordinate runtime은 실행 도중 자체 업데이트하지 않는다.

Provider CLI/runtime version을 명시적으로 고정한다.

```text
runtime version
model
configuration
```

을 telemetry에 기록한다.

Update는 별도 dependency maintenance 작업에서만 수행한다.

---

# 39. Network

Reviewer가 network를 필요로 하지 않으면 차단한다.

Researcher 역할처럼 network가 필요한 경우에만 허용한다.

Coding agent가 dependency 설치를 위해 network가 필요할 수 있지만:

```text
dependency install
arbitrary external write
credentialed service operation
```

을 구분한다.

---

# 40. Destructive Actions

Subordinate agent는 다음을 독자적으로 수행할 수 없다.

```text
force push
published tag 변경
repository visibility 변경
secret rotation
external deployment
production write
local PC privileged access
database destructive migration
unrelated process kill
```

이런 action은 parent와 사용자의 permission policy를 따른다.

---

# 41. Release Authority

Subordinate agent는 product version이나 release 상태를 최종 확정할 수 없다.

다음을 할 수 있는 것은 Codex Parent뿐이다.

```text
READY_TO_RELEASE 판정
release commit 생성 결정
annotated product tag 생성 결정
release manifest 최종 승인
```

Worker가 tag를 생성하면 안 된다.

---

# 42. Observability

Subagent orchestration 결과는 향후 adaptive router를 위해 지속적으로 저장한다.

권장 위치:

```text
runs/subagents/
```

또는 Dataset Foundry의 별도 metadata store.

Git에는 aggregate report만 넣는다.

예:

```text
reports/subagent-orchestration.md
```

Raw transcript 전체를 Git에 저장하지 않는다.

---

# 43. Orchestration Metrics

최소 다음을 집계한다.

```text
jobs by provider
jobs by model
jobs by role

CommandCode : OpenCode actual ratio

success rate
first-pass success
rework rate
timeout rate
schema-invalid rate

mean/p50/p95 latency
reported token usage
reported monetary usage

tests passed
critic defect findings
accepted findings

result commits accepted
result commits rejected
```

---

# 44. Provider Ratio Report

각 reporting window에서:

$$
R =
\frac{U_{command}}
     {U_{opencode}}
$$

를 계산한다.

목표:

$$
R \approx 2
$$

단 provider unavailable 또는 hard routing override가 발생한 window에서는 deviation 이유를 기록한다.

예:

```yaml
ratio:
  target: 2.0
  actual: 2.42

deviation:
  reason:
    - OpenCode unavailable for 3 jobs
```

비율을 맞추기 위한 의미 없는 호출은 절대 만들지 않는다.

---

# 45. Quality Overrides Ratio

다음 상황에서는 2:1보다 품질을 우선한다.

```text
critical security review
release blocking issue
model-specific capability
independent dissent required
provider-specific failure
high-risk data rights decision
```

예:

Command Code가 구현한 고위험 변경에는 OpenCode critic을 추가할 수 있다.

이는 OpenCode usage가 일시적으로 1/3 이상이 되더라도 허용한다.

---

# 46. No Artificial Work

Quota를 소비하거나 2:1을 맞추기 위해 다음을 하지 않는다.

```text
이미 검증된 작업 재호출
가치 없는 duplicate review
trivial test generation
불필요한 rephrasing
동일 code를 여러 모델에 이유 없이 생성
```

모든 subordinate call에는 구체적인 decision value가 있어야 한다.

---

# 47. Subagent Invocation Logging

모든 invocation에 다음을 남긴다.

```text
why this subagent was called
why this role was selected
why this provider was selected
what evidence is expected
```

예:

```yaml
routing_reason:
  role: critic
  provider: opencode
  reason: >
    Independent read-only critique of a Command Code implementation
    before canonical merge.
```

---

# 48. Context Minimization

Subordinate agent에게 repository 전체 context를 무조건 제공하지 않는다.

필요한:

```text
goal
constraints
relevant files
ADR
schema
failure logs
base commit
```

만 제공한다.

Context가 부족하면 subordinate가 추가 read를 요청하거나 repository에서 읽을 수 있다.

API key, unrelated personal memory, unrelated project context는 넣지 않는다.

---

# 49. User Memory Boundary

향후 Miku Agent의 사용자 memory가 engineering workflow와 연결되더라도 subordinate coding agents에는 필요한 project memory만 전달한다.

개인 사용자 기억 전체를 coding provider에 전달하지 않는다.

원칙:

```text
least-context
least-privilege
```

---

# 50. Final Rule

Subordinate agent는 조언자·실행자·비평가다.

Codex Parent는 판단자다.

실제 테스트와 repository evidence가 최종 source of truth다.

기본 agent 사용 비율은:

$$
\boxed{
Command\ Code : OpenCode = 2 : 1
}
$$

로 유지한다.

단 이 비율보다 항상 다음이 우선한다.

```text
correctness
security
evidence
task suitability
user intent
```

비율을 지키기 위해 프로젝트 품질을 낮추지 않는다.

