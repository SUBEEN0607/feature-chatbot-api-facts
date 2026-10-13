# 인허가 매칭 검토 목록

`license_matches_to_check.csv` 는 소상공인 점포와 인허가 기록을 자동으로 연결하지 못했거나 확신이 낮은 점포입니다.

- `address_only`: 같은 도로명 주소에 영업 중인 인허가가 있지만 상호가 다릅니다. 같은 건물의 다른 가게일 수도, 상호를 바꾼 같은 가게일 수도 있습니다.
- `none`: 후보가 없습니다.

검토 방법 (멤버 1명이 한 줄씩):

1. 지도나 로드뷰, 현장 방문으로 점포를 확인합니다. 네이버 플레이스 등 자동 수집은 하지 않습니다.
2. `verdict` 에 `same_business` (같은 가게), `different_business` (다른 가게), `unsure` 중 하나를 씁니다.
3. 다른 인허가 번호가 맞다면 `correct_license_id` 에 적습니다.
4. `checked_by` 에 이름, `checked_on` 에 날짜 (YYYY-MM-DD), 필요하면 `note` 를 씁니다.

엑셀에서 열어도 한글이 깨지지 않도록 UTF-8 BOM 으로 저장되어 있습니다. 저장할 때 CSV UTF-8 형식을 유지해 주세요.

# AI 추정 초안 검토 (`ai_drafts.csv`)

`python -m agents.guesstimate` 가 만든 기준값 초안입니다. AI는 이 파일과 `accepted_patch.yaml` 에만 씁니다. `guesstimate.xlsx`, `hero_base.yaml`, `shocks.yaml` 은 코드로 막혀 있어 절대 바뀌지 않습니다.

- `current_*`: 지금 워크북 값. `draft_*`: AI 초안. `draft_sources`: 초안이 인용한 출처 id.
- 명령줄에서는 모델 없이 mock 초안만 만듭니다 (현재 값을 그대로 두고, 읽어 볼 근거 후보를 붙임). 실제 모델 초안은 API `POST /review/drafts/{criterion_id}` 로 한 번에 한 기준씩 만듭니다.

검토 방법:

1. 근거 후보를 읽고 초안 숫자와 계산 근거가 맞는지 확인합니다. 고칠 부분은 `draft_*` 칸을 직접 고쳐도 됩니다.
2. `reviewed_by` 에 이름, `accept` 에 `Y` (반영) 또는 `N` (반영 안 함), 필요하면 `review_note` 를 씁니다.
3. `python -m agents.guesstimate --apply-reviewed` 를 실행하면 `reviewed_by` 가 있고 `accept=Y` 인 행만 `accepted_patch.yaml` 로 모입니다. 워크북 반영은 사람이 `research/build_workbook.py --apply-patch research/review/accepted_patch.yaml` 로 합니다 (검토된 행만 반영되고 ChangeLog 시트에 기록됨).
4. 같은 기준을 다시 초안으로 만들 때 숫자가 바뀌면 그 행의 검토 칸은 비워집니다. 새 숫자는 다시 검토해야 합니다.

# 구글 시트 검토표 (`Team 1 고깃집 검토표`)

팀원은 엑셀 대신 Team 1 AI Assignment 폴더의 구글 시트에서 맡은 값을 검토합니다. 시트 주소와 id 는 `review_sheet.json` 에 있습니다. 사용법은 시트의 안내 탭에 있습니다.

- 이름 탭에는 `docs/TASKS.md` 에서 그 사람이 맡은 값만 있습니다. 회색 칸(현재 값)은 저장소 값이고, 흰 칸(확인 결과부터 검토자까지)만 팀원이 씁니다.
- 검토자와 확인 결과(맞음 또는 수정)가 모두 있는 행만 반영됩니다. 수정은 낮음 ≤ 기본 ≤ 높음 숫자와 근거 링크(출처 번호 S.. 또는 URL)가 있어야 합니다.

반영 (저장소 담당자):

```
.venv/bin/python research/sync_review_sheet.py            # 미리 보기: 무엇이 바뀌는지, 거절된 행과 이유 (아무것도 쓰지 않음)
.venv/bin/python research/sync_review_sheet.py --apply    # accepted_patch.yaml 작성, 새 URL 은 ontology/sources.csv 에 추가,
                                                          # build_workbook.py --apply-patch 로 guesstimate.xlsx 와 hero_base.yaml 재생성 (ChangeLog 기록)
.venv/bin/python research/sync_review_sheet.py --apply --stamp   # 반영된 행의 반영됨 칸에 날짜 기록
.venv/bin/python research/sync_review_sheet.py --refresh  # 워크북이 바뀐 뒤 시트의 현재 칸만 다시 씀 (팀원 입력 칸은 건드리지 않음)
```

`accepted_patch.yaml` 은 AI 초안 승인 행(filled_by AI)과 검토표 행(filled_by 검토표)을 함께 담습니다. 두 도구 모두 상대 행을 지우지 않고, 같은 기준이면 검토표가 우선합니다. `season_params:`, `sim_params:`, `BM` 으로 시작하는 행은 시뮬레이션 설정이라 패치의 `sim_assumptions` 에 보고만 되고, 사람이 직접 반영합니다.
