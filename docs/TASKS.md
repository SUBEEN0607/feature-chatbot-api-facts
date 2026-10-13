# 팀 과제 (리서치와 데이터)

지금은 모두가 리서치와 데이터를 맡습니다. 한 사람이 숫자 묶음 하나를 책임지고, 모두 같은 3단계로 일합니다. 팀원용 기준 문서는 Notion "TODO TEAM AI PJT" 페이지이고, 이 파일은 그 내용을 저장소 쪽에서 똑같이 보여 줍니다. 둘이 다르면 Notion 이 맞습니다.

공통 규칙

- 숫자마다 출처나 계산 근거가 있어야 함, 없으면 신뢰도 L 로 두고 그렇다고 적기
- AI가 찾아 준 숫자는 반드시 직접 출처를 열어 확인하고 reviewed_by 에 본인 이름 기입
- 네이버 플레이스, 캐치테이블, 테이블링은 자동 수집 금지 (약관 위반), 직접 보고 손으로 소량만 기록
- 가게 이름, 사장님 성함, 전화번호는 적지 않고 T01 같은 번호로만 기록
- 유료 자료나 유료 API 는 쓰지 않음
- 저장소에 올리는 일(push)은 정해진 사람이 함

---

## 3단계 루프: 찾기, 확인, 기입

1. **찾기**: 맡은 값마다 무료 공개 자료(논문, 정부 통계, 기사), 현장 관찰, 지인 질문으로 숫자를 찾음
2. **확인**: 출처를 직접 열어 숫자와 조건(지역, 연도, 단위)이 맞는지 보고, 낮음, 보통, 높음 세 값과 계산 근거 한 줄을 정함
3. **기입**: 구글 시트 `Team 1 고깃집 검토표` (Team 1 AI Assignment 폴더) 의 내 이름 탭에서 확인 결과(맞음 또는 수정), 수정 값, 근거 링크, 메모, 검토자를 채움, 검토자가 있는 행만 반영되고 저장소 반영은 김건희가 함 (방법은 시트의 안내 탭, 저장소 쪽은 `research/review/README.md`)

HeroStore 에 행이 없는 값(표에 `season_params.yaml` 로 표시)은 엑셀이 아니라 시뮬레이션 설정 파일에 있습니다. 이런 값은 숫자와 출처만 정리해서 Claude 에게 넣어 달라고 하면 됩니다.

Claude에게 이렇게 말하기 (값 하나마다 반복)

```
나는 [이름]이고 [값 이름]을 맡았어
research/guesstimate.xlsx 의 HeroStore 에서 [criterion_id] 행의 지금 값, 근거, 출처를 보여줘
이 값을 뒷받침할 무료 공개 자료를 세 개만 찾아 주고, 각각 링크와 원문 문장, 지역과 연도를 같이 보여줘
내가 링크를 열어 확인한 것만 골라서 낮음, 보통, 높음과 계산 근거 한 줄을 제안해줘
내가 좋다고 하면 검토표 내 탭의 그 행에 넣을 확인 결과, 수정 낮음, 수정 기본, 수정 높음, 근거 링크, 메모를 한 줄로 정리해줘
```

이미 AI가 만든 초안이 있으면 먼저 `research/review/ai_drafts.csv` 에서 그 행을 보여 달라고 해도 됩니다.

---

## 오하영: 손님과 상권

| 값 | 찾을 곳 (criterion_id 또는 파일과 키) |
|---|---|
| 월 손님 수 | `sto_table_turns`, `sto_occupancy`, `sto_open_days` (월 손님 수 `drv_covers` 는 이 셋으로 계산됨) |
| 한 팀 인원 | `mkt_party_size`, `seg_twenties_party_factor`, `seg_office_party_factor`, `seg_family_party_factor` |
| 체류 시간 | `drv_dwell_time`, `seg_twenties_dwell_factor`, `seg_office_dwell_factor`, `seg_family_dwell_factor` |
| 대기 인내 | `mkt_patience`, `drv_balk_rate`, `seg_twenties_patience_factor`, `seg_office_patience_factor`, `seg_family_patience_factor` |
| 시간대 비중 | `reg_evening_share`, `seg_twenties_early_mult`, `seg_twenties_late_mult`, `seg_office_early_mult`, `seg_office_late_mult`, `seg_family_early_mult`, `seg_family_late_mult` |

함께 할 일

- 인허가 매칭 7건 확인: `research/review/license_matches_to_check.csv` 의 7개 행을 지도와 로드뷰로 확인하고 verdict, correct_license_id, checked_by, checked_on 기입 (방법은 `research/review/README.md`)
- 생존 곡선 한 장: `data/processed/survival_wide.json` 으로 돼지고기 구이집(이름 기준)과 나머지 한식의 생존 곡선을 그리고, 표본 수와 p값 0.091, 생존자 편향 주의를 세 문장으로 정리

완료 기준

- 표의 모든 행에 reviewed_by 와 source_id (없으면 confidence L 과 이유) 기입
- 인허가 7건 모두 verdict 기입
- 생존 곡선 그림 한 장과 설명 세 문장

## 김정연: 원가와 가격

| 값 | 찾을 곳 (criterion_id 또는 파일과 키) |
|---|---|
| 원육별 원가 | `cst_meat_cost_per_portion`, `prd_meat_origin`, `season_params.yaml` 의 `meat_grade.imported`, `meat_grade.domestic`, `meat_grade.aged` |
| 판매가 | `prd_meat_price`, `prd_portion_grams` |
| 소주 | `prd_alcohol_price`, `cst_alcohol_cost_per_bottle`, `prd_alcohol_per_cover` |
| 반찬 | `svc_banchan_count`, `cst_banchan_cost_per_cover` |
| 공과금 | `cst_utilities` |
| 기타 비용 | `cst_other_opex`, `cst_side_cost_ratio` |
| 카드 수수료 | `cst_card_fee_rate`, `cst_card_share` |

함께 할 일

- 메뉴판 가격 현장 기록 3곳: 대학로 삼겹살집 3곳의 메뉴판에서 1인분 가격과 중량, 소주 가격, 식사 메뉴 가격을 기록, 가게는 T01 부터 번호로만 적고 사진은 허락을 받은 경우에만 찍기

완료 기준

- 표의 모든 행에 reviewed_by 와 source_id 기입
- 현장 3곳 기록을 Sources 시트에 "현장 관찰, 날짜, T번호" 로 추가하고 판매가 행의 근거로 인용

## 박재현: 인력과 운영

| 값 | 찾을 곳 (criterion_id 또는 파일과 키) |
|---|---|
| 인건비 | `sto_parttime_wage`, `cst_employee_wage`, `cst_owner_imputed_wage`, `cst_holiday_pay_factor` |
| 알바 수 | `sto_parttimers`, `sto_parttime_shift_hours`, `sto_employees` |
| 응대 시간 | `sim/params.py` 의 `svc_order_min`, `svc_reorder_min`, `svc_refill_per_bottle_min`, `svc_pay_min`, `svc_clear_min`, `svc_staff_grill_min`, `season_params.yaml` 의 `staff.table_tasks_min` |
| 영업일수 | `sto_open_days` |
| 영업시간 | `drv_open_hours`, `season_params.yaml` 의 `hours.demand` |
| 임대료 | `drv_rent`, Benchmarks 시트 `BM42` 부터 `BM45` (혜화동, 서울, 전국 임대료) |

함께 할 일

- 알바 경험이 있는 지인에게 질문: 고깃집 알바를 해 본 지인 2명 이상에게 인터뷰 가이드 Q17, Q18 (`research/interview/owner_interview_guide.md`) 을 물어 응대 시간과 인원을 기록, 이름은 적지 않음
- Windows 에서 `scripts/dev.ps1` 을 한 번 실제로 실행하고 막힌 곳과 해결 방법을 `docs/SETUP.md` 의 Windows 절에 기록 (지금까지 한 번도 실행된 적 없음)

완료 기준

- 표의 모든 행에 reviewed_by 와 source_id 기입 (응대 시간은 지인 답변을 근거로 Claude 에게 반영 요청)
- 지인 2명 이상 답변 기록
- dev.ps1 실행 결과가 SETUP 에 기록됨

## 이지우: 평판과 손님 경험

| 값 | 찾을 곳 (criterion_id 또는 파일과 키) |
|---|---|
| 리뷰 작성 비율 | `mkt_review_count`, `season_params.yaml` 의 `reviews.base_prob`, `reviews.segment_mult` |
| 리뷰 이벤트 효과 | `mkt_review_event`, `season_params.yaml` 의 `marketing.review_event_share`, `marketing.review_event_star_bias`, `marketing.review_event_prob_mult`, `marketing.review_event_skeptic_prob` |
| 평점과 매출 | `mkt_review_rating`, `season_params.yaml` 의 `demand.rating_per_star` (지금 근거 S03) |
| 만족 요인 | `prd_food_quality`, `svc_cleanliness`, `season_params.yaml` 의 `satisfaction.quality_weight`, `satisfaction.price_over_weight`, `satisfaction.wait_per_10min`, `satisfaction.clean_weight` |

함께 할 일

- 한 시즌 플레이 후 어색한 점 5개: 게임을 자유 플레이로 여섯 달 끝까지 해 보고, 숫자나 리뷰, 사장님 말이 현실과 어색한 점 5개를 화면 사진과 함께 정리 (무엇이, 왜 어색한지, 현실에서는 어떤지)

완료 기준

- 표의 모든 행에 reviewed_by 와 source_id 기입
- 어색한 점 5개 목록과 화면 사진

## 김건희: 통합

- 팀원이 채운 값과 출처를 확인하고 워크북 반영을 승인
- AI 초안(`research/review/ai_drafts.csv`) 가운데 검토 승인된 행을 워크북에 반영
- 반영 뒤 시뮬레이션과 게임 숫자가 어떻게 바뀌었는지 확인하고 발표 흐름에 반영

---

## 선택 과제 (여유가 있을 때)

예전 역할별 과제 가운데 아직 남은 것들입니다. 맡을 사람이 생기면 Claude 에게 이 제목을 그대로 말하고 시작하면 됩니다.

- Docker 에서 Postgres 와 pgvector 검증: SQLite 와 같은 결과가 나오는지 비교 (`docker-compose.yml`, `db/`, `rag/retrieve.py`)
- 팀 GitHub 자동 테스트: PR 마다 테스트가 도는 워크플로 초안, push 는 정해진 사람이 함
- 접근성 점검: 키보드만으로 한 달 진행, axe 검사에서 심각한 위반 0건 (`web/src/v2/`)
- 번들 크기 줄이기: 3D 장면 청크 크기 전후 비교 (`web/`)
- 모바일(390px) 플레이 흐름: 가려지거나 잘리는 요소 0건
- 기준 달 보정 리포트: 평소 한 달이 앵커 범위 안인지 표로 정리 (`sim/calibrate.py`, `sim/sensitivity.py`)
