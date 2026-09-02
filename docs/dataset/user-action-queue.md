# User Action Queue

현재 자동화로 대신할 수 없는 항목이다.

- Licensed Miku voice/SVS engine의 output 학습·가공 조건과 evidence를 확인한다.
- Speech-like Korean script bundle을 licensed engine에서 manual render하고 output filename/hash를 intake한다.
- 실제 target voice audio의 transcript, segment, speaker consistency와 quality tier를 human review한다.
- 권리자가 제공한 license text 또는 permission evidence로 `unknown` source를 명시적으로 판정한다.
- Pilot review UI의 waveform/segment editor 요구를 검토한다.

이 작업 전에는 target voice effective speech hours를 0으로 유지한다.
