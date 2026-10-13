# 개발 환경 설정 (SETUP)

두 가지 방법이 있습니다. 팀원 대부분은 **A. Docker** 를 쓰면 되고, Docker 없이 빠르게 돌려보려면 **B. 로컬 Python** 을 쓰면 됩니다. 두 방법 모두 같은 코드와 같은 테이블 구조를 씁니다.

| | A. Docker | B. 로컬 Python (Docker 없음) |
|---|---|---|
| DB | SQLite 파일 (이미지에 적재된 채로 들어 있음). 선택: Postgres 16 + pgvector | SQLite 파일 `data/twin.db` |
| 벡터 검색 | numpy 코사인 유사도 (Postgres 선택 시 pgvector) | numpy 코사인 유사도 |
| 용도 | 팀원 PC에서 바로 실행, 데모 | 개인 개발, 테스트 |

## 공통 준비

1. Git 저장소를 받습니다.
2. 서울 열린데이터광장 API 키가 필요한 사람은 저장소 최상위에 `.env` 파일을 만들고 한 줄을 넣습니다. `.env` 는 Git에 올라가지 않습니다.

```
SEOUL_API_KEY=여기에_키
```

키는 데이터를 새로 받을 때만 필요합니다. `data/processed/` 에 처리된 데이터가 이미 커밋되어 있으므로, DB 적재와 API 실행에는 키가 없어도 됩니다. `.env` 대신 환경 변수 `SEOUL_API_KEY` 로 넘겨도 됩니다 (예: `SEOUL_API_KEY=... make pipelines`).

3. 처음 한 번은 오래 걸립니다: Python 패키지(torch 포함), 임베딩 모델 intfloat/multilingual-e5-small (약 470MB, 무료, 키 없음), 웹 패키지(`npm install`). 공공데이터를 새로 받는 경우 소상공인 상가정보 압축 파일도 약 350MB 입니다 (`data/raw/` 에 저장, Git 제외).
4. 브라우저 자동 점검(`make e2e`)을 쓸 사람만 한 번 설치합니다: `cd web && npx playwright-core install chromium --only-shell`

## A. Docker (Windows / Mac)

Windows는 단계별 안내 `docs/WINDOWS-DOCKER.md` 를 보세요 (WSL2, Docker Desktop, 자주 나는 오류).
Mac은 Docker Desktop을 설치하고 실행해 둡니다.

### 실행

```bash
docker compose up -d --build       # 처음에는 이미지 빌드 때문에 오래 걸림 (torch, 임베딩 모델, DB 적재, 시즌 캐시)
docker compose ps                  # api 가 healthy, web 이 Up 이면 준비 완료
```

- API 문서: http://localhost:8000/docs , 상태 확인: http://localhost:8000/health
- 웹: http://localhost:5173
- DB 적재, RAG 임베딩, 시즌 미리보기 캐시, 임베딩 모델이 모두 이미지 안에 들어 있어서 따로 실행할 명령이 없고, 실행 중에 인터넷도 필요 없습니다
- 코드를 바꾼 뒤에는 `docker compose up -d --build` 로 다시 빌드합니다 (소스 폴더를 컨테이너에 연결하지 않음. 코드를 고치면서 바로 보려면 B 방법)
- 포트를 바꾸려면 `API_PORT=8100 WEB_PORT=5273 docker compose up -d` (또는 `.env` 에 `API_PORT=8100` 같은 줄). 웹이 부르는 API 주소와 API의 허용 주소가 함께 맞춰짐
- 끄기: `docker compose down`
- 설정 확인만 할 때: `docker compose config`

Postgres + pgvector 로 돌리려면 (API가 시작할 때 DB 적재와 임베딩을 함):

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.postgres.yml down -v   # DB 볼륨까지 지움
```

### Windows 실행 기록 (2026-10-05, 박재현)

- `docs/WINDOWS-DOCKER.md` 대로 저장소 폴더에서 `docker compose up -d --build` 실행, 성공
- 확인한 것: 시연 4개월, 자유 플레이 6개월, 결과 화면, CSV, 리포트, 비교 화면 모두 정상. 가게 둘러보기를 거친 뒤에 진행해도 오류 없음
- 같은 PC 에서 B (로컬 Python) 로는 멈추거나 오류가 났던 단계 (e5 임베딩, 첫 미리보기 60초 초과, 마지막 달 409, B 절 Windows 기록 참고) 가 Docker 에서는 생기지 않음 → Windows 팀원은 Docker 로 실행하는 것을 권장
- 저장소 폴더 안에서 실행해야 함. 다른 폴더에서는 `no configuration file provided` 오류
- 로컬 Python 서버 (dev.ps1) 가 켜져 있으면 먼저 Ctrl+C 로 끄기 (8000, 5173 포트가 겹침)
- `docker compose logs api` 에 5초마다 찍히는 `127.0.0.1 GET /health` 는 컨테이너 상태 점검이라 정상. 브라우저에서 온 요청은 `172.18.0.1` 로 찍힘
- 권장: 빌드 중에도 e5 임베딩이 돌기 때문에 Docker 가 쓰는 메모리와 CPU 에 상한을 둠. `%USERPROFILE%\.wslconfig` 에 아래 세 줄을 넣고 `wsl --shutdown` 후 Docker Desktop 재시작

```
[wsl2]
memory=8GB
processors=4
```

## B. 로컬 Python (Docker 없음)

Python 3.11 또는 3.12를 권장합니다 (3.14는 일부 패키지가 아직 불안정).

```bash
python3.12 -m venv .venv              # 3.12가 없으면 python3.11. uv가 있으면: uv venv --python 3.12
source .venv/bin/activate
pip install -r requirements.txt
python -m db.load                     # data/twin.db (SQLite) 생성 및 적재
python -m rag.ingest                  # 임베딩 (intfloat/multilingual-e5-small, CPU, 무료)
uvicorn api.main:app --reload         # http://localhost:8000/docs
```

## 테스트

```bash
python -m pytest tests sim/tests -q   # 임시 SQLite + mock LLM 으로 실행, 외부 호출 없음
python -m db.load --selftest          # 임시 DB에 두 번 적재해서 결과가 같은지 확인
python -m pipelines.run_all --selftest   # 공공데이터 파이프라인 1분기 1상권 점검 (키 필요)
```

### Windows (PowerShell): `scripts/dev.ps1` 실행 기록 (2026-10-05, 박재현)

Windows PC (RAM 32GB, Python 3.12.14 via uv) 에서 dev.ps1 을 처음으로 실제 실행한 결과입니다.

#### 실행한 순서 (성공)

```powershell
cd C:\Users\<사용자>\SDIC\sdic-persona-team1
uv venv --seed --python 3.12 .venv        # uv 가 없으면: py -3.12 -m venv .venv  (막힌 곳 1)
$env:RAG_EMBEDDER = "hash"                 # 막힌 곳 2
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

- `-ExecutionPolicy Bypass`: Windows 기본 설정이 .ps1 실행을 막아서 이번 실행에만 허용
- 결과: 패키지 설치, DB 적재 (테이블 11개), RAG 임베딩 (문서 168개, 조각 480개), API http://localhost:8000, 웹 http://localhost:5173 정상
- 게임: 시즌 시작, 미리보기, 한 달 플레이, 시즌 리포트, report.html, 트윈 인터뷰 응답 정상
- 실행 뒤 `git status` 에 바뀐 저장소 파일 없음 (`.venv`, `web\node_modules`, `data\twin.db`, `data\cache` 는 Git 제외 대상)

#### 막힌 곳과 해결

1. **uv 가 설치된 PC: 패키지 설치 단계에서 멈출 수 있음**
   - dev.ps1 은 uv 가 있으면 `uv venv` 로 가상환경을 만들고 `python -m pip` 로 설치하는데, `uv venv` 로 만든 가상환경에는 pip 가 없음 (dev.sh 는 `uv pip install` 을 써서 문제 없음)
   - 해결: dev.ps1 전에 `uv venv --seed --python 3.12 .venv` 로 pip 까지 넣어 만들어 둠. dev.ps1 은 `.venv\Scripts\python.exe` 가 이미 있으면 새로 만들지 않음
   - 같은 이유로 위 B 절 안내의 `uv venv --python 3.12` 도 `--seed` 를 붙여야 그다음 `pip install` 이 가상환경 안에 설치됨

2. **RAG 임베딩 단계 (`[dev] embedding RAG corpus`) 에서 PC 전체가 멈춤**
   - 2회 재현, 강제 종료 필요. `$env:OMP_NUM_THREADS = "4"` 로 CPU 스레드를 줄여도 똑같이 멈춤. 원인 미확정 (RAM 32GB 라 메모리 부족 가능성은 낮음)
   - 같은 PC 의 Docker (A 절 Windows 기록) 에서는 같은 e5 임베딩이 정상 → Windows 에서 torch 를 직접 돌릴 때만 생기는 문제로 보임
   - 해결: `$env:RAG_EMBEDDER = "hash"` (테스트용 임베딩, torch 를 쓰지 않음). 게임과 시뮬레이션은 그대로이고 사장님 채팅의 근거 검색 품질만 낮아짐
   - 주의: hash 로 적재했으면 서버도 hash 로 켜야 함. 검색은 같은 방식으로 만든 조각만 찾아서, 다르면 경고 없이 0건이 됨. 새 PowerShell 창마다 다시 설정하거나 계정에 고정: `[Environment]::SetEnvironmentVariable("RAG_EMBEDDER", "hash", "User")`

3. **강제 종료 뒤 `SyntaxError: source code string cannot contain null bytes`**
   - 멈춤 직전에 설치되던 패키지 파일이 0 으로 채워져 깨짐 (`.venv\Lib\site-packages\sentence_transformers\__init__.py`). 저장소 파일은 이상 없음 (`git status` 로 확인)
   - 해결: 가상환경과 DB 를 지우고 캐시 없이 다시 설치

   ```powershell
   Remove-Item -Recurse -Force .venv
   Remove-Item data\twin.db, data\twin.db-journal
   $env:PIP_NO_CACHE_DIR = "1"
   uv venv --seed --no-cache --python 3.12 .venv
   ```

4. **첫 미리보기에서 화면이 멈춘 것처럼 보이고 `signal is aborted without reason`**
   - 웹은 요청 하나를 60초까지 기다림 (`web/src/v2/api.ts`). dev.ps1 에는 dev.sh 의 시즌 미리보기 캐시 단계 (`sim.warm`) 가 없어서, 첫 미리보기가 캐시를 만드느라 60초를 넘기면 웹이 요청을 끊음
   - 이때 시연 모드 4개월이 1개월 결과만 나왔고, 한 번 지나간 뒤에는 정상 작동
   - 해결: 서버를 켜기 전에 `.\.venv\Scripts\python.exe -m sim.warm` 를 한 번 실행 (이번에는 시도하지 않음, dev.sh 와 같은 단계). 캐시 확인만: `-m sim.warm --check`

5. **자유 플레이 마지막 달 정산에서 `HTTP 409 {"detail":"season is over (closed or all months played)"}`**
   - 서버 DB 에는 마지막 달까지 6개월이 모두 저장되어 있었음. 마지막 달 응답이 60초를 넘겨 웹이 먼저 끊었고 (4번과 같은 제한), 다시 누르자 서버가 "이미 끝난 시즌" 으로 409 를 돌려줌. 가게 둘러보기와는 관계 없음
   - 결과 보기: 서버가 켜져 있으면 `http://localhost:8000/season/<시즌 id>/report.html` (시즌 id 는 오류 문구 안의 `/season/` 뒤 12자리)

6. **강제 종료 뒤 `git status` 에 `data/twin.db-journal`**
   - DB 작업이 끊기며 남은 임시 파일. 지워도 됨 (`.gitignore` 에 아직 없는 항목)

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/twin.db` | Docker 기본도 SQLite. `docker-compose.postgres.yml` 을 함께 쓰면 Postgres 주소가 들어감 |
| `LLM_BACKEND` | `mock` | `mock` (오프라인 템플릿 응답), `gemini` (Google AI Studio 무료 등급), `claude_cli` (건희 Mac 데모 전용) |
| `GEMINI_API_KEY` | 없음 | `gemini` 용 키. 환경 변수, 저장소 `.env`, 상위 폴더 `.env` 순서로 찾고 출력하지 않음 |
| `LLM_MODEL` | 백엔드별 | `gemini` 기본값 `gemini-3.1-flash-lite`. Flash, Flash-Lite 모델만 허용 (pro, image, tts 거부) |
| `GEMINI_FALLBACK_MODEL` | `gemini-2.5-flash` | 기본 모델이 과부하(503)일 때 한 번 시도하는 모델 (일일 한도가 따로 있음) |
| `GEMINI_TIMEOUT_S` / `GEMINI_RETRIES` | `15` / `1` | 요청 하나의 제한 시간과 재시도 횟수. 넘으면 사장님 답은 템플릿으로 나감 |
| `GEMINI_MIN_INTERVAL_S` | `4` | 실제 호출 사이 최소 간격 (무료 등급 분당 한도 보호) |
| `LLM_SESSION_CAP` | `30` | 세션당 LLM 호출 상한 |
| `LLM_RATE_PER_MIN` | `6` | 1분당 LLM 호출 상한 |
| `LLM_CLAUDE_CWD` | `~/.cache/team-gogi-llm` | `claude_cli` 작업 폴더 (저장소 밖, 빈 폴더) |
| `RAG_EMBEDDER` | `e5` | `hash` 는 테스트 전용 (모델 다운로드 없음) |
| `SEOUL_API_KEY` | 없음 | 데이터를 새로 받을 때만 |

## LLM 사용 규칙 (코드에 강제되어 있음)

- 모든 호출은 `agents/llm.py` 한 곳을 거칩니다. API 요청 하나당 호출 한 번만 허용되고, 반복문이나 일괄 호출 함수는 없습니다.
- 세션당 호출 상한과 1분당 상한이 있고, 같은 질문은 디스크 캐시에서 먼저 찾습니다.
- 기본값은 `mock` 이라 아무 설정 없이 실행하면 외부 모델을 부르지 않습니다.
- `claude_cli` 는 건희 Mac에서 호스트로 직접 띄운 API에서만 동작하고 (컨테이너 안에는 `claude` 가 없음), Opus 모델 이름이 아니면 거부합니다.
- 팀원 PC와 데모는 `gemini` (무료 등급) 를 쓸 수 있습니다: `LLM_BACKEND=gemini` 로 API를 띄우면 됩니다. 키는 헤더로만 보내고 로그나 오류 문구에 넣지 않습니다.
- Gemini 무료 등급은 모델마다 하루 요청 한도가 있고 한국 시간 16:00에 초기화됩니다. `LLM_BACKEND=gemini` 이면 시즌에서 한 달을 진행할 때마다 월말 문장에도 한 번씩 호출하므로, 데모 당일에는 점검용 호출을 아껴 두세요.
- 사장님 채팅은 실제 모델 답의 숫자를 입력값(가게 숫자, 시뮬레이션 결과, 근거 자료, 질문)과 대조합니다. 입력에 없는 숫자가 나오거나 모델이 응답하지 않으면 같은 숫자로 만든 템플릿 답을 보내고 `backend` 에 그 사실을 적습니다 (화면에는 연습 응답으로 표시).

### 사장님 채팅 정확도 점검

- `make chat-eval`: `tests/chat_eval/questions.yaml` 의 질문 33개(숫자, 원가, 영업, 상권, 레버, 시즌, 함정 질문)를 mock 백엔드로 묻고, 답과 검색(정답 문서가 상위 5개에 있는지)을 채점합니다. 외부 호출 없음
- `make chat-eval-gemini`: 같은 질문을 Gemini 무료 등급으로 묻습니다 (질문당 한 번, 11초 간격). `make test` 에는 들어가지 않습니다
- 정답은 저장소 자료에서만 가져옵니다: 시뮬레이션 평소 달, `research/hero_base.yaml`, `data/processed`. 질문마다 출처가 적혀 있습니다
- 채팅이 인용하는 숫자 목록은 `agents/store_facts.py` 한 곳에서 만듭니다. `rag.ingest` 는 가게 입력값 한 줄마다 검색 조각을 하나씩 만들므로, 이 브랜치를 받은 뒤에는 `make ingest` 를 한 번 다시 실행하세요

### `claude_cli` 격리

저장소 안에서 `claude -p` 를 실행하면 상위 폴더의 CLAUDE.md, 메모리, 훅이 함께 로드됩니다. 이를 막기 위해 어댑터는 다음처럼 실행합니다.

- 작업 폴더: `~/.cache/team-gogi-llm/` (없으면 만듦, `LLM_CLAUDE_CWD` 로 변경 가능). 이 폴더나 상위 폴더에 `.git`, `CLAUDE.md`, `.claude`, `.mcp.json` 이 있으면 호출을 거부합니다.
- 실행 인자 (Claude Code 2.1.285 의 `claude --help` 로 확인):

```
claude -p --model opus --safe-mode --setting-sources project --strict-mcp-config --tools "" \
  --disable-slash-commands --no-session-persistence --no-chrome --system-prompt "<텍스트 전용 안내>"
```

- 환경 변수 `CLAUDE_CODE_SAFE_MODE=1` 도 함께 넘깁니다.
- `--safe-mode` 는 CLAUDE.md, 스킬, 플러그인, 훅, MCP 서버를 모두 끄고, `--tools ""` 는 도구를 전부 끕니다. 페르소나는 텍스트 답변만 필요합니다.
- `--bare` 는 쓰지 않습니다. 이 모드는 `ANTHROPIC_API_KEY` (유료 API) 만 읽고 구독 로그인을 쓰지 않기 때문입니다. 이 버전에는 max-turns 인자가 없고, 도구가 없으므로 한 번의 응답으로 끝납니다.
- 테스트는 실제 `claude` 를 한 번도 실행하지 않습니다. 가짜 `claude` 스크립트로 작업 폴더, 인자, 환경 변수를 확인합니다.

## 폴더 역할

| 폴더 | 내용 |
|---|---|
| `industry/` | 업종 설정 yaml (업종 코드, 상권, 분기) |
| `pipelines/` | 공공데이터 수집 및 가공 (`docs/DATA.md` 참고) |
| `ontology/` | 기준(노드), 인과 관계(엣지), 출처 |
| `research/` | 추정치 워크북, 히어로 매장 값, 충격 목록 |
| `db/` | 테이블 정의 (`models.py`), Postgres DDL (`schema.sql`, 자동 생성), 적재 (`load.py`) |
| `rag/` | 문서 코퍼스, 임베딩, 검색 |
| `agents/` | LLM 어댑터, 사장 에이전트, 페르소나 채팅 |
| `api/` | FastAPI 서버 |
| `sim/` | 시뮬레이션 |
| `web/` | 프론트엔드 (예정) |

`db/models.py` 를 바꾸면 `python -m db.schema_sql` 로 `db/schema.sql` 을 다시 만들어야 테스트가 통과합니다.

## 통합 점검과 데모 준비

```bash
make e2e                               # API와 웹을 화면 없이 켜고, 한 달 플레이와 사장님 대화를 자동 확인한 뒤 모두 끔
python -m agents.prewarm --dry-run     # 데모 날 미리 보낼 질문 목록과 캐시 키만 보여 줌 (아무것도 보내지 않음)
make warm                              # 시즌 미리보기 캐시를 미리 만듦 (모델을 바꾼 뒤 한 번 약 1분 30초, 이미 있으면 바로 끝남)
```

- 시즌 미리보기(`/season/{id}/preview`)는 기준 계획의 시뮬레이션 평균에 맞춰 보정합니다. 이 평균은 `data/cache/` 에 저장되고, `research/*.yaml` 이나 `sim/` 코드를 바꾸면 다시 만들어야 합니다. 캐시가 없으면 첫 미리보기가 1분 넘게 걸리므로, 데모 전에는 `make warm` 을 실행하세요. `scripts/dev.sh` 와 `make e2e` 는 캐시가 없거나 오래됐으면 서버를 켜기 전에 자동으로 만듭니다. 확인만 하려면 `python -m sim.warm --check`.
- Docker 이미지는 빌드할 때 캐시를 만들어 넣으므로 따로 할 일이 없습니다.

- 8000, 5173 포트를 다른 서버(예: 데모)가 쓰고 있으면 다른 포트로 실행합니다: `API_PORT=8100 WEB_PORT=5273 scripts/dev.sh`, `API_PORT=8100 WEB_PORT=5273 make e2e`. 이때 웹이 부를 API 주소(`VITE_API_BASE`)와 API의 허용 주소(`CORS_ORIGINS`)도 자동으로 맞춰지고, 스크립트는 자기가 켠 서버만 끕니다.
- `agents.prewarm` 은 `--dry-run` 없이는 실행되지 않습니다. 실제로 보내는 일은 데모 날 건희가 화면이나 API로 한 번에 한 질문씩 합니다. 같은 질문 문장, 같은 사건과 대응일 때만 캐시가 맞으므로, 데이터를 바꾼 뒤에는 목록을 다시 확인하세요.
