# Production image for `ocom-reader web`.
#
# Serves Reader's own documentation (README, CHANGELOG, docs/) — never a Vector
# repository. The public deployment must only ever show "examples without
# corporate data" (see OCOM-Infrastructure's Private-by-Default architecture
# rule); Reader's web UI has no Vector wiring today, so this is also the only
# content it is currently capable of serving.

# ---- Builder: build a wheel, keep build tooling out of the runtime image ----
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /build/dist

# ---- Runtime ----
FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system ocom && useradd --system --gid ocom --home /app ocom

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# The document set the public instance indexes: this repository's own
# documentation, nothing else. No Vector repository is ever mounted or baked
# into this image.
COPY README.md CHANGELOG.md ./docroot/
COPY READER_*.md ./docroot/
COPY docs/ ./docroot/docs/

# .ocom/ is Reader's own regenerable index cache for docroot/ — writable by
# the non-root user, not by anyone else.
RUN mkdir -p ./docroot/.ocom \
    && chown -R ocom:ocom /app

USER ocom

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=2)" || exit 1

ENTRYPOINT ["ocom-reader", "web", "--host", "0.0.0.0", "--port", "8765", "--repo", "/app/docroot"]
