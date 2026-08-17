FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV FFMPEG_BIN=/usr/bin/ffmpeg
ENV FFPROBE_BIN=/usr/bin/ffprobe

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py ./
COPY media ./media

ENV MEDIA_DIR=/app/media
ENV OUTPUT_DIR=/tmp/prikol_out
RUN mkdir -p /app/media /tmp/prikol_out

CMD ["python", "bot.py"]
