FROM python:3.11-bullseye as builder

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -U pip && \
    python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED True

WORKDIR /workspace

COPY --from=builder /wheels /wheels

RUN python -m pip install --no-cache-dir -U pip && \
    python -m pip install --no-cache /wheels/*

COPY . /workspace/

CMD ["python", "app.py"]
