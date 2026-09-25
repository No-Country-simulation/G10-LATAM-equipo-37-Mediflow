FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Dependencias a nivel sistema operativo para OCR multimodal (español, portugués e inglés)
# necesarias para la ingestión y lectura de PDFs escaneados y fotos de recetas.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    curl \
    git \
    make \
    && rm -rf /var/lib/apt/lists/*
