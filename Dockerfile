FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py ./

ENV MEDIA_DIR=/app/media
ENV OUTPUT_DIR=/tmp/prikol_out
RUN mkdir -p /app/media /tmp/prikol_out

CMD ["python", "bot.py"]
