FROM python:3.12-slim

ARG INSTALL_OCR=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////data/contracts.db \
    UPLOAD_DIR=/data/uploads/contracts

WORKDIR /app

RUN apt-get update \
    && if [ "$INSTALL_OCR" = "true" ]; then \
        apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-por; \
    fi \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-ocr.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_OCR" = "true" ]; then pip install -r requirements-ocr.txt; fi

COPY app ./app

RUN mkdir -p /data/uploads/contracts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
