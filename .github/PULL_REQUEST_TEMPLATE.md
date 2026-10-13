## 무엇을 바꿨나요

<!-- 한두 줄로 -->

## 왜 바꿨나요

<!-- 관련 과제가 있으면 docs/TASKS.md 의 번호 (예: B1) -->

## 확인한 것

- [ ] `make test` 통과 (mock LLM, 임시 SQLite)
- [ ] 화면을 바꿨다면 `make e2e` 또는 `web/scripts/playthrough.mjs` 통과, 스크린샷 첨부
- [ ] 데이터나 DB 구조를 바꿨다면 `python -m db.load --selftest` 통과
- [ ] `db/models.py` 를 바꿨다면 `python -m db.schema_sql` 로 `db/schema.sql` 다시 생성

## 숫자와 근거

- [ ] 새로 넣거나 바꾼 숫자마다 출처 id (`ontology/sources.csv`) 또는 계산 근거가 있음
- [ ] AI가 만든 값은 `filled_by` 가 AI 이고, 검토한 사람이 `reviewed_by` 에 이름을 남김
- [ ] 자동 수집 금지 사이트(네이버 플레이스, 캐치테이블, 테이블링)에서 긁어 온 데이터 없음

## 보안

- [ ] API 키, 비밀번호, `.env` 내용이 diff 에 없음
- [ ] 유료 API 를 부르는 코드 없음 (LLM 호출은 `agents/llm.py` 하나로만)
