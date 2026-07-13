FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/dist/prism_agent-*.whl /tmp/
RUN pip install --no-cache-dir /tmp/prism_agent-*.whl
EXPOSE 8000
CMD ["prism", "api-server", "--host", "0.0.0.0", "--port", "8000"]
