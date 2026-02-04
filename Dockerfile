FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional, keep minimal)
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Default envs (override in Railway Variables)
ENV TZ=Asia/Yerevan
ENV DB_PATH=/data/bot.db

# Railway will provide PORT sometimes; bot uses polling so PORT is unused.
CMD ["python", "-m", "bot.main"]
