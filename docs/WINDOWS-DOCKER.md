# Windows에서 Docker로 실행하기

게임 화면(웹)과 API를 Docker 컨테이너 두 개로 띄웁니다. Python, Node.js 설치는 필요 없습니다.
DB, 문서 임베딩, 시즌 캐시, 임베딩 모델이 모두 이미지 안에 들어가므로 명령 한 줄이면 됩니다.

## 1. 준비 (처음 한 번)

- Windows 10 22H2 이상 또는 Windows 11
- 디스크 여유 공간 10GB 이상 (이미지 약 4GB와 빌드 캐시)
- PowerShell을 **관리자 권한**으로 열고 WSL2 설치 후 재부팅

```powershell
wsl --install
wsl --update
```

- Docker Desktop for Windows 설치: https://www.docker.com/products/docker-desktop/ (학생, 개인 용도 무료)
- Docker Desktop 실행 후 Settings, General 에서 **Use the WSL 2 based engine** 켜기
- 왼쪽 아래에 **Engine running** 이 보일 때까지 기다리기 (Docker Desktop이 켜져 있어야 모든 명령이 동작함)
- Git for Windows 설치: https://git-scm.com/download/win

확인 (PowerShell, 관리자 아니어도 됨):

```powershell
docker version
docker compose version
```

`Server:` 부분까지 나오면 준비 완료입니다. `Client:` 만 나오고 오류가 나면 아래 오류 1번을 보세요.

## 2. 저장소 받기

경로에 한글과 공백이 없는 폴더를 권장합니다 (예: `C:\dev`).

```powershell
mkdir C:\dev -Force
cd C:\dev
git clone -c core.autocrlf=false https://github.com/skkusdic/sdic-persona-team1.git team-gogi
cd team-gogi
```

- `-c core.autocrlf=false` 는 파일 줄바꿈을 리눅스 형식(LF) 그대로 받는 설정
- 저장소의 `.gitattributes` 도 같은 일을 하므로, 이미 받아 둔 저장소라면 `git pull` 만 해도 됨

## 3. 실행

```powershell
docker compose up -d --build
```

- 처음 한 번은 오래 걸림: torch, 임베딩 모델(약 470MB) 다운로드, DB 적재, 시즌 캐시 계산을 빌드 중에 함
- 중간에 멈춘 것처럼 보여도 `season cache: building` 단계는 계산 중이니 기다리기
- 두 번째부터는 캐시를 써서 바로 켜짐

## 4. 잘 되는지 확인

```powershell
docker compose ps
```

- `api` 가 `Up (healthy)`, `web` 이 `Up` 이면 성공
- 브라우저에서 http://localhost:8000/health 를 열면 `{"ok":true,"db":"sqlite","backend":"mock",...}` 가 보임
- 브라우저에서 http://localhost:5173 을 열면 게임 화면이 나옴. 자유 플레이로 한 달을 진행해 보기
- API 문서: http://localhost:8000/docs

로그 보기:

```powershell
docker compose logs api --tail 50
docker compose logs web --tail 50
```

## 5. 끄기, 다시 켜기, 코드 바꾼 뒤

```powershell
docker compose down              # 끄기
docker compose up -d             # 다시 켜기 (빌드 없이)
docker compose up -d --build     # git pull 이나 코드 수정 뒤 (바뀐 부분만 다시 빌드)
```

컨테이너는 소스 폴더를 직접 보지 않으므로, 코드를 고친 뒤에는 꼭 `--build` 를 붙입니다.

## 6. 자주 나는 오류

### 오류 1. Docker 엔진에 연결이 안 됨

```
error during connect: ... open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified
Docker Desktop is unable to start / WSL 2 installation is incomplete
```

- Docker Desktop이 꺼져 있거나 아직 시작 중인 상태. Docker Desktop을 열고 **Engine running** 이 될 때까지 기다린 뒤 다시 실행
- WSL2 문제면 관리자 PowerShell에서 `wsl --update` 후 재부팅
- `Virtualization support not detected` 가 나오면 BIOS에서 가상화(Intel VT-x 또는 AMD SVM) 켜기

### 오류 2. 포트가 이미 사용 중

```
Bind for 127.0.0.1:8000 failed: port is already allocated
ports are not available: ... An attempt was made to access a socket in a way forbidden by its access permissions
```

- 다른 프로그램이 8000 이나 5173 을 쓰고 있거나, Windows가 그 포트 대역을 예약해 둔 상태
- 다른 포트로 실행하면 해결. 웹이 부르는 API 주소도 자동으로 맞춰짐

```powershell
$env:API_PORT=8100; $env:WEB_PORT=5273; docker compose up -d
```

- 이후 주소는 http://localhost:5273 (웹), http://localhost:8100/health (API)
- 매번 입력하기 싫으면 저장소 최상위에 `.env` 파일을 만들고 `API_PORT=8100` 과 `WEB_PORT=5273` 두 줄 넣기
- Windows 예약 포트 확인: `netsh interface ipv4 show excludedportrange protocol=tcp`

### 오류 3. 빌드 중 다운로드 실패 또는 디스크 부족

```
ReadTimeoutError / Connection reset / failed to resolve source metadata
no space left on device
```

- 학교 와이파이처럼 불안정한 네트워크에서 자주 생김. 같은 명령 `docker compose up -d --build` 를 다시 실행하면 이미 받은 단계는 건너뛰고 이어서 진행
- 디스크 부족이면 여유 공간을 만들고 `docker builder prune` 으로 오래된 빌드 캐시 정리

### 오류 4. 줄바꿈(CRLF) 오류

```
/usr/bin/env: 'bash\r': No such file or directory
/bin/sh^M: bad interpreter
```

- Windows에서 받은 저장소를 WSL 안에서 `scripts/dev.sh` 로 실행할 때 생김 (Docker 실행은 이미지 안에서 자동으로 고쳐지므로 해당 없음)
- 2번 단계처럼 `-c core.autocrlf=false` 로 다시 clone 하기

### 화면은 뜨는데 데이터가 안 나올 때

- `docker compose ps` 에서 `api` 가 `healthy` 인지 확인. `starting` 이면 조금 기다리기
- 포트를 바꿨다면 `API_PORT`, `WEB_PORT` 를 설정한 같은 창에서 `docker compose up -d` 를 실행했는지 확인
- 그래도 안 되면 `docker compose logs api --tail 50` 결과를 팀 채팅방에 그대로 붙여 넣기
