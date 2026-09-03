# Source Intake

발견, metadata 등록, 획득, quarantine 저장, training 승격은 서로 다른 단계다. Intake 대상은 `$MIKU_DATA_ROOT/intake`, project-configured directory 또는 사용자가 준 path로 제한한다. 원래 파일을 삭제·이동·덮어쓰지 않는다.

Source에는 origin, creator, acquisition method/time, content hash, language, character, parent work, derivative family와 독립 상태를 기록한다. 공개 접근 가능성은 이용 권한이 아니다. DRM, paywall, login protection 또는 service restriction 우회는 금지한다.

Rights의 자유문 설명인 `allowed_use`는 training 허가 판정에 사용하지 않는다. 근거가 검토된 source만
`training_allowed=true`를 명시하며, 생략 또는 false는 fail-closed로 training 승격을 막는다.
