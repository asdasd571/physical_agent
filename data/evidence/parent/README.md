# 모기업 공개 수요 근거 입력

`candidate_id="COMMON"`, `kind="parent_demand"`인 record를 담은 JSON을 둔다.
공통 자료에는 후보의 수행·시험·인증 record를 넣지 않는다.
`task_id`, `doc_type="parent"`, `public_document=true`, `source_ids`가 필요하다.
연결 SourceRecord는 실제 모기업 공개 PDF의 doc_id, 원문 페이지, SHA256, 경로, 발췌를 가진다.

공개 문서에서 확인한 작업 수요만 입력한다. 내부 수요를 안다고 가정하지 않는다.
후보 수행 근거가 없는 모기업 문서만으로 S2를 인정하지 않는다.
입력 최상위 JSON과 SourceRecord 계약은 [담당 모듈 안내](../../../reporting/README.md)를 참고한다.
