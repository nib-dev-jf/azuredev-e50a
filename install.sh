#!/bin/sh
set -e

echo "[install] Detecting Python..."
PY_CMD="python3"
PIP_CMD="pip3"
if ! command -v "$PY_CMD" >/dev/null 2>&1; then
	PY_CMD="python"
fi
if ! command -v "$PIP_CMD" >/dev/null 2>&1; then
	PIP_CMD="pip"
fi

echo "[install] Using $PY_CMD and $PIP_CMD"

echo "[install] Installing CLI requirements (run_model.py)"
$PIP_CMD install -r requirements.txt

echo "[install] Installing API (FastAPI) requirements"
$PIP_CMD install -r src/requirements.txt

echo "[install] Installing Streamlit (dev) requirements"
if [ -f requirements-dev.txt ]; then
	$PIP_CMD install -r requirements-dev.txt
else
	echo "[install] requirements-dev.txt not found, skipping"
fi

echo "[install] Checking for pnpm to build React frontend"
if command -v pnpm >/dev/null 2>&1; then
	echo "[install] pnpm found: $(pnpm -v)"
	echo "[install] Installing and building frontend"
	(cd src/frontend && pnpm install && pnpm build)
else
	echo "[install] pnpm not found. To build the frontend later:"
	echo "         - Install Node.js and pnpm"
	echo "         - cd src/frontend && pnpm install && pnpm build"
fi

echo "[install] Done. Next steps:"
echo "  - Streamlit UI:    streamlit run ./streamlit_app/app.py"
echo "  - Backend API:     uvicorn src.api.main:create_app --factory --port 8000"
echo "  - Frontend (dev):  cd src/frontend && pnpm dev"