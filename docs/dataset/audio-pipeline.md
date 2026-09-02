# Audio Pipeline

원본 sample rate와 codec을 보존하고 normalization, segmentation, separation, ASR와 alignment 결과는 모두 새 object/transform이다. 기본 segment target은 3~8초, core 허용 범위는 2~12초이며 short utterance는 별도 category다. VAD만으로 음소 경계를 자르지 않고 transcript punctuation, alignment와 review를 결합한다.

Singing source는 `singing_aux`로 분리하며 speech effective hours에 포함하지 않는다. Separator 비교는 ground-truth stem이 없으면 SDR을 실제 정확도로 주장하지 않고 leakage, artifact, intelligibility, speaker preservation과 human AB를 기록한다. 현재 pilot tone은 decoder/object/review 경로 검증용 quarantine이며 speech가 아니다.
