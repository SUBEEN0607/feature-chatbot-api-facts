# API image: code, SQLite DB, RAG index, season cache and the e5 embedder are all baked in, so
# `docker compose up` serves immediately with no bind mount, no download and no manual load step.
# Works on linux/arm64 (Mac) and linux/amd64 (Windows / WSL2); no arch-pinned images or wheels.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/opt/hf
# CPU-only torch first, so sentence-transformers does not pull the multi-GB CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# the e5 embedder (~470 MB) in its own layer, so code changes never download it again
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('intfloat/multilingual-e5-small', device='cpu')"
COPY . .
# a Windows checkout made before .gitattributes (core.autocrlf=true) has CRLF files: make code and config LF
RUN find . -type f \( -name '*.sh' -o -name '*.py' -o -name '*.yaml' -o -name '*.yml' -o -name '*.sql' \) \
      -exec sed -i 's/\r$//' {} +
# SQLite DB + RAG index + season preview cache (data/cache, sim.warm) so the first request is instant
RUN python -m db.load && python -m rag.ingest && python -m sim.warm
# runtime: never ask the Hugging Face Hub (model is baked), mock LLM unless compose says otherwise
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_BACKEND=mock
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=60s --retries=30 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
