# 기술·후보 수행 근거 입력

확정 후보별 `*.json`을 둔다. 형식과 실행법은 [담당 모듈 안내](../../../reporting/README.md)를 참고한다.
지원 record kind는 `technology`, `founders`, `paper`, `trial`, `pilot`, `funding`, `task`, `certification`이다.
필드 계약은 [tech 프롬프트](../../../prompts/tech.md)와 [synergy 프롬프트](../../../prompts/synergy.md)에 있다.

실제 후보와 원문이 확정되지 않아 가상 데이터를 이 수집 폴더에 넣지 않았다.
시험 fixture는 `tests/test_tech.py`, 보고서 전용 가상 데이터는 `reporting/demo.py`에 있다.
파일의 candidate_id는 확정 Candidate와 일치해야 한다.
정부 과제는 전체 사업비가 아니라 기업 귀속 정부 연구비만 입력한다.
누락 원값을 0으로 바꾸지 않는다. 민감정보나 API 키를 근거 파일에 저장하지 않는다.
