# GPU Processing

## RTX 3080

Inventory: RTX 3080 10,240 MiB. 관측 시 다른 `ollama/llama-server`가 약 7,594 MiB를 사용했다. Process를 종료하지 않았고 Foundry GPU job도 실행하지 않았다. PCM decode probe 10개는 CPU에서 실행했다.

## RTX 5090

SSH read-only inventory만 수행했다. RTX 5090 32,607 MiB이며 dataset job 0개 executed다. Job `4e1a5606-e2e9-4110-a04f-214b4498316b`은 input/source/worker manifest package로 준비되어 `waiting_for_lease`에 있다. Grant가 없으므로 stage/run/transfer를 수행하지 않았다.

V0.1.0 process를 종료하거나 repository, environment, system package를 수정하지 않았다.
