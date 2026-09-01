# System Context

```text
Flutter mobile ---- HTTPS / WS events / WS audio ----+
Unity desktop ---- HTTPS / WS events / WS audio ----+--> Backend policy boundary
Clerk ------------ signed identity token ----------+         |
                                                        +-----+-----+
                                                        |           |
                                                 Voice runtime   Memory
                                                        |           |
                                                 Codex workspace Scheduler
```

클라이언트는 UI·reflex·offline fallback을 제공하고 main agent를 포함하지 않는다. Backend는 identity, grant, ownership과 permission을 검증한다. Voice runtime, memory, Codex, scheduler는 V0.1.0 이후 서버에 존재한다. 외부 API는 HTTPS, realtime audio와 event는 분리된 WebSocket, 내부 service RPC는 gRPC다.

Trust boundary는 client/server, backend/model output, host/container, canonical memory/projection, private repository/external data storage에 놓인다. server 결과와 local model 판단이 충돌하면 server가 우선한다.

