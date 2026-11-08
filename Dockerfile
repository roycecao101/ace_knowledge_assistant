FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && useradd --uid 10001 --create-home ace
COPY backend/*.py ./backend/
COPY frontend/*.html frontend/*.css frontend/*.js ./frontend/
COPY frontend/assets/ace-logo.webp ./frontend/assets/ace-logo.webp
USER ace
CMD ["python", "-m", "backend.serve"]
