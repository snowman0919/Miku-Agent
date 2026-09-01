# Client Experience

## Mobile

Flutter 앱 안에서 캐릭터를 인터페이스 중심으로 만난다. VRM surface, voice, touch, expression, lip sync, chat/history, push, memory control, account UI를 제공한다. Renderer는 Flutter renderer, embedded Unity, native bridge를 후속 검증한다. 앱 framework 결정은 Flutter로 유지한다.

## Desktop

Unity 캐릭터가 OS 공간에 존재한다. Transparent/frameless window, drag, touch/click reaction, click-through region, screen edge, multi-monitor, tray, global shortcut, idle/sleep, desktop notification reaction을 목표로 한다.

두 client는 UI code를 공유하지 않는다. Agent/audio/memory/authentication/character state/reaction/VRM asset schema와 character-runtime contract만 공유한다. 약 2~4B local multimodal model은 UI intent, reflex, 제한된 offline fallback, 간단한 recognition, 안전한 local tool, server 장애 설명만 담당한다. 복잡한 추론, memory 통합, Codex, web research, main voice는 server 우선이며 충돌 시 server 결과를 따른다. 전체 local memory 접근은 명시 권한이 있을 때만 허용한다.

