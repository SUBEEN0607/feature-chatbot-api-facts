# SDIC 2기 미니 과제, Team 1

소상공인 업종별 사업자 페르소나 도출 및 UI/UX 프로토타이핑 (2026-09-30 세션 과제)

- 팀장: 김건희
- 팀원: 이지우, 오하영, 김정연, 박재현
- 과제 수행 Rule: GitHub Repo 필수 사용, RAG 구축 및 실제 활용, Repo와 Drive 운영, 아키텍처 체계화 및 문서화
- 발표: 리서치 과정, 전체 산출물 시연, DB와 아키텍처, GitHub 활용
- 역할별 시작 과제: `docs/TASKS.md` · 기술 스택: `docs/STACK.md` · 리서치 방법: `docs/RESEARCH.md`

# 대학로 삼겹살집 디지털 트윈 (Team 고깃집)

대학로(혜화역) 상권 3120012 의 가상 독립 삼겹살집을 공공데이터와 추정치로 만든 디지털 트윈입니다. 충격(원가 상승, 비 오는 날, 경쟁점 개점 등)을 고르고 사장님의 대응을 고르면, 시뮬레이션 결과와 그날 밤의 3D 재현을 볼 수 있습니다.

**모든 매장 수치는 팀원 검토 전의 예시 추정치입니다.**

## 실행

필요한 것: Git, Python 3.11 또는 3.12, Node.js 20 이상. API 키는 필요 없습니다 (처리된 공공데이터가 저장소에 들어 있음).

```bash
git clone <저장소 주소> team-gogi && cd team-gogi
scripts/dev.sh          # Mac, Linux, WSL. Windows PowerShell 은 .\scripts\dev.ps1
```

처음 실행할 때는 패키지 설치(torch 포함)와 임베딩 모델 다운로드(약 470MB) 때문에 오래 걸립니다. 두 번째부터는 `scripts/dev.sh --no-load` 로 바로 켤 수 있습니다.

가상환경 설치, DB 적재, 문서 임베딩 후 API(http://localhost:8000/docs)와 웹(http://localhost:5173)이 켜집니다. 브라우저는 직접 여세요. Docker를 쓰려면 `docker compose up -d --build` 한 줄이면 됩니다 (`docs/SETUP.md`, Windows는 `docs/WINDOWS-DOCKER.md`). 테스트는 `make test` 입니다.

## 게임 흐름 (v2)

1. **시연 모드:** 발표자 설명과 함께 4개월 이야기를 봅니다. 인터넷과 API 없이 됩니다.
2. **자유 플레이:** 대학로 지도에서 가게로 들어가 6개월을 운영합니다. 매달 이번 달 사건을 보고, 운영 계획판의 레버 14개(가격, 원육, 메뉴, 반찬, 직원 굽기, 알바 수, 영업시간, 점심, 야장, 마케팅, 리뷰 이벤트, 단체 예약, 위생)를 정하면 예상 영업이익과 범위가 바로 보입니다.
3. **한 달 재생과 정산:** 3D 가게에서 그달 토요일 밤을 보고, 영업이익이 어디서 왔는지, 운의 범위, 현금, 평판, 손님 리뷰를 확인합니다. 리뷰를 누르면 그 손님에게 질문할 수 있습니다.
4. **시즌 끝:** 현금이 두 달 연속 0 아래이거나 매출이 크게 줄면 폐업, 6개월을 버티면 생존. 평소 계획과 비교합니다.
5. **트윈 인터뷰:** 실제 사장님 인터뷰와 같은 15문항에 사장님 트윈이 답합니다.

## English

A store-level digital twin of a composite pork BBQ restaurant in Seoul's 대학로 district, built from free
public data and sourced guesstimates, with a discrete-event simulation, a shock-and-response game UI, a 3D
replay and grounded LLM personas (mock by default, no paid APIs). Run `scripts/dev.sh`.

| Doc | Content |
|---|---|
| `docs/STACK.md` | tools and skills per layer, now and next (Korean) |
| `docs/GAME-V2-SPEC.md` | v2 game design and data contracts |
| `docs/ARCHITECTURE.md` | system map, layers, data flow, DB tables, AI use and guardrails, porting to another 업종 |
| `docs/SETUP.md` | Docker and no-Docker setup (Korean) |
| `docs/WINDOWS-DOCKER.md` | Docker on Windows, step by step (Korean) |
| `docs/DATA.md` | every public dataset, fields, counts, pitfalls |
| `docs/SIMULATION.md`, `docs/EVENT_LOG.md` | simulation model and replay event format |
| `research/review/` | store-license matches for members to confirm |
