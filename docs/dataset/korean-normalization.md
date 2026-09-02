# Korean Normalization

`raw_text`, `spoken_text`, `normalized_text`를 보존하고 rule version을 붙인다. 초기 `tn-ko-v1`은 숫자, 날짜·시간, 금액, 단위, 영문 약어, 제품명, URL·path와 code token을 다룬다. 모호한 발음은 하나로 덮어쓰지 않고 alternative로 유지한다.

Script coverage는 초중종성, 받침·겹받침, 연음·비음화·유음화·구개음화·된소리·ㅎ 변화, 종결형과 짧은 맞장구부터 긴 기술 설명까지 포함한다. 실제 target persona pronunciation은 human render/review 전까지 미결정이다.
