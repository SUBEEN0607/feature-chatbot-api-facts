# ChangeUp: 예비 창업자 시뮬레이터 (목업)

고깃집을 열어 볼까 고민하는 20~40대가 **여는 돈, 동네 손님, 6개월 현금 흐름**을 미리 굴려 보는 웹 목업입니다.
서울 25개 구의 공개 자료로 동네를 비교하고, 가게를 직접 꾸민 뒤, 하루 단위로 6개월을 운영해 봅니다.

**목업입니다.** 지역 매출, 점포 수, 날씨, 공휴일은 공개 자료를 가공한 값이고, 월세와 비용 대부분은 가정이거나 예시값입니다.
어떤 숫자가 실측이고 어떤 숫자가 가정인지는 앱의 `#/sources` 페이지에 모두 적혀 있습니다.

## 흐름

1. **내 조건**: 업종, 열고 싶은 구, 가진 돈, 나이대를 질문 하나씩 답합니다. (카페는 자료 준비 중)
2. **동네 분석**: 서울 지도에서 구별 매출 지수, 고깃집 수, 폐업률을 견주고 여는 데 드는 돈을 봅니다.
3. **가게 꾸미기**: 가진 돈 안에서 평수, 테이블, 설비, 직원을 정합니다. 처음에는 추천 배치로 시작하고, 아래에서 열기 전 점검(본전 손님 수, 회수 시점, 나쁜 일 4가지)을 봅니다.
4. **시뮬레이션**: 여는 달을 골라 180일을 하루씩 재생합니다. 되감기, 빨리 감기, 사건과 선택, 현금 흐름 기록이 있습니다.

## 실행

Node.js 20 이상이 필요합니다. API 서버와 키는 필요 없습니다 (처리된 자료가 `web/public/mock/`에 들어 있습니다).

```bash
cd web
npm install
npm run dev -- --port 5174
```

- 앱: http://127.0.0.1:5174/
- 출처 장부(운영자용): http://127.0.0.1:5174/#/sources

## 자료 다시 만들기

| 파일 | 만드는 스크립트 | 원자료 |
|---|---|---|
| `web/public/mock/gu_stats.json` | `python -m pipelines.build_gu_stats` | 서울시 상권분석서비스(추정매출, 점포), 소상공인 상가정보 (원자료는 `data/raw/`, 저장소에 없음) |
| `web/public/mock/weather_seoul.json`, `holidays.json` | `python -m pipelines.fetch_weather` | 기상청 ASOS 일자료, 한국천문연구원 특일 정보 (공공데이터포털 인증키 필요, `.env.example` 참고) |
| `web/public/mock/seoul_gu.json` | (일회성 변환) | southkorea/seoul-maps 행정구역 경계 |

## 문서

- `DESIGN.md`: 화면 규칙 (색, 글자, 지도, 하지 않는 것)
- `web/src/mock/model.ts`, `sim.ts`: 월 단위 계산식과 하루 단위 시뮬레이션
- `docs/TWIN-README.md`: 원본 "대학로 삼겹살집 디지털 트윈" README

## 어디서 왔나

이 저장소는 SDIC 2기 Team 1의 [대학로 삼겹살집 디지털 트윈](https://github.com/skkusdic/sdic-persona-team1)(팀장 김건희, 팀원 이지우, 오하영, 김정연, 박재현)에서 가지를 쳐 예비 창업자용으로 바꾼 것입니다.
`agents/`, `api/`, `sim/`, `rag/`, `research/`, `industry/`, `ontology/`, 기존 `web/` 화면은 원본의 코드와 자료이고, 원본에 라이선스 파일이 없어 별도 라이선스를 붙이지 않았습니다.
`web/src/mock/`, `pipelines/build_gu_stats.py`, `pipelines/fetch_weather.py`, `DESIGN.md`가 이번에 새로 만든 부분입니다.

## 키와 개인정보

- `.env`는 저장소에 올리지 않습니다. `.env.example`만 올라가 있습니다.
- `research/review/review_sheet.json`(팀 Drive 시트 아이디)은 제외했습니다.
- `data/processed/licenses*.csv`는 지방행정 인허가 공개 자료로, 상호와 주소가 들어 있습니다.
