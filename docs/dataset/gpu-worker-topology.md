# GPU Worker Topology

RTX 3080은 canonical registry와 object store의 유일한 writer다. Core, separation, ASR, embedding과 quality worker environment를 분리하고 각 job에 input manifest, pinned tool/model revision, output hashes, resource metrics와 structured error를 요구한다. GPU lock은 `$MIKU_DATA_ROOT/jobs/local/gpu0.lock`이다.

RTX 5090은 manifest-bound remote worker다. Explicit grant, input digest, code commit과 environment binding 없이는 실행하지 않는다. Remote는 canonical DB path를 받지 않고 disposable cache에 결과를 만든다. 3080이 전송 후 hash를 다시 확인해 local transaction으로 승격한다. V0.1.0 CONDITIONAL 결과를 production readiness로 해석하지 않는다.
