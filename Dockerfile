# Browser + Python image with OS deps for Chromium
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY pyproject.toml README.md DESIGN.md ./
COPY config ./config
COPY src ./src

RUN pip install --no-cache-dir -e ".[gemini]" \
    && playwright install chromium

ENV TRAILHEAD_AGENT_HEADLESS=1
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["trailhead-agent"]
CMD ["doctor", "--json"]
