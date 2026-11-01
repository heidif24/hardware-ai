FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
ENV QT_QPA_PLATFORM=offscreen
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    kicad freecad \
    gcc gcc-avr avr-libc gcc-arm-none-eabi binutils-arm-none-eabi \
    cmake ninja-build make git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /data/jobs && useradd --create-home --uid 10001 worker && chown -R worker:worker /app /data
USER worker
ENV JOBS_ROOT=/data/jobs
ENV PORT=8080
EXPOSE 8080
CMD ["python3","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8080"]
