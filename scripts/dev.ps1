# One-command local run without Docker (Windows PowerShell 5+/7).
#   .\scripts\dev.ps1              set up .venv, load DB + RAG, start API :8000 and web :5173
#   $env:API_PORT=8100; $env:WEB_PORT=5273; .\scripts\dev.ps1   other ports
#   .\scripts\dev.ps1 -NoWeb       API only
#   .\scripts\dev.ps1 -NoLoad      skip db.load / rag.ingest
# Ctrl-C stops both servers. Nothing opens a browser; visit http://localhost:5173 yourself.
# WSL users: run scripts/dev.sh inside Ubuntu instead (faster file access).
# "running scripts is disabled on this system": powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
# Docker instead (no Python/Node install): docs/WINDOWS-DOCKER.md
param([switch]$NoWeb, [switch]$NoLoad)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not $env:LLM_BACKEND) { $env:LLM_BACKEND = "mock" }
$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
$WebPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { "5173" }
if (-not $env:VITE_API_BASE) { $env:VITE_API_BASE = "http://localhost:$ApiPort" }
if (-not $env:CORS_ORIGINS) { $env:CORS_ORIGINS = "http://localhost:$WebPort,http://127.0.0.1:$WebPort" }
$env:BROWSER = "none"
$env:PYTHONUTF8 = "1"   # Korean JSON/yaml read without encoding= would otherwise decode as cp949
$Py = Join-Path $Root ".venv\Scripts\python.exe"

function Say($m) { Write-Host "[dev] $m" -ForegroundColor Cyan }

# 1. Python env
if (-not (Test-Path $Py)) {
  if (Get-Command uv -ErrorAction SilentlyContinue) { Say "creating .venv with uv"; uv venv --python 3.12 .venv }
  elseif (Get-Command py -ErrorAction SilentlyContinue) { Say "creating .venv with py -3.12"; py -3.12 -m venv .venv }
  else { Say "creating .venv with python"; python -m venv .venv }
}
$ReqHash = (Get-FileHash requirements.txt -Algorithm SHA256).Hash.Substring(0, 16)
$HashFile = Join-Path $Root ".venv\.req-hash"
if (-not (Test-Path $HashFile) -or (Get-Content $HashFile) -ne $ReqHash) {
  Say "installing requirements (first run pulls torch for local embeddings)"
  & $Py -m pip install -q --upgrade pip
  & $Py -m pip install -q -r requirements.txt
  if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
  Set-Content $HashFile $ReqHash
}

# 2. Database + RAG
if (-not $NoLoad) {
  Say "loading DB"; & $Py -m db.load; if ($LASTEXITCODE -ne 0) { throw "db.load failed" }
  Say "embedding RAG corpus"; & $Py -m rag.ingest; if ($LASTEXITCODE -ne 0) { throw "rag.ingest failed" }
}

# 3. Servers
$procs = @()
try {
  Say "API  http://localhost:$ApiPort/docs  (LLM_BACKEND=$env:LLM_BACKEND)"
  $procs += Start-Process -FilePath $Py -ArgumentList "-m","uvicorn","api.main:app","--host","127.0.0.1","--port",$ApiPort -NoNewWindow -PassThru
  if (-not $NoWeb -and (Test-Path "web\package.json")) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
      if (-not (Test-Path "web\node_modules")) { Say "npm install (web)"; Push-Location web; npm install --no-fund --no-audit; Pop-Location }
      Say "web  http://localhost:$WebPort"
      $procs += Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev","--","--host","127.0.0.1","--port",$WebPort,"--strictPort" -WorkingDirectory (Join-Path $Root "web") -NoNewWindow -PassThru
    } else { Say "npm not found: skipping web (install Node.js 20+)" }
  }
  Wait-Process -Id ($procs | ForEach-Object { $_.Id })
}
finally {
  Say "stopping"
  foreach ($p in $procs) { if (-not $p.HasExited) { taskkill /PID $p.Id /T /F | Out-Null } }
}
