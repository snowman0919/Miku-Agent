# Animation and Embodiment

## Hybrid controller

- Layer 0, procedural physiology: blink, breathing, eye saccade, micro head motion, weight shift, spring bone.
- Layer 1, FSM: IDLE, LISTENING, THINKING, SPEAKING, TOOL_WORK, WAITING, NOTIFYING, SLEEPING, ERROR.
- Layer 2, behavior tree: state별 idle variation, gaze, touch, notification response를 선택한다.
- Layer 3, high-level tools: emotion, gesture, gaze target, posture, touch acknowledgement, state transition을 요청한다.

LLM/local sLLM이 per-frame bone transform을 직접 생성하지 않는다. Token latency는 frame deadline을 만족하지 못하고, 비결정 출력은 pose stability를 해치며, 충돌·관절 제한·취소·replay를 통제하기 어렵기 때문이다.

## Voice-body synchronization

Phoneme/viseme timing, pitch, energy, emotion, speech rate, semantic emphasis를 timestamped cue로 변환해 face와 body layer에 공급한다. Audio가 source clock이며 late cue는 bounded correction을 적용한다. Touch region은 client가 hit-test하고 즉각적인 local reflex를 낸 뒤, 필요할 때만 semantic event를 server cognition에 보낸다. Server는 고수준 reaction을 제안하지만 안전하고 부드러운 실행은 local controller가 담당한다.

