FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && chmod +x entrypoint.sh mcp_entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000 8001

# No image-level HEALTHCHECK: the same image backs two services on different
# ports (backend :8000, mcp :8001), so each one declares its own in compose.

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
