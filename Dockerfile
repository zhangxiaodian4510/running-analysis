FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8080 \
    APP_SHOW=0

WORKDIR /app

# 依赖（先装，利用层缓存）
COPY requirements.txt .
RUN pip install -r requirements.txt

# 应用代码
COPY . .

# 数据库与上传文件存放处（用卷挂载以持久化）
VOLUME ["/app/data"]

EXPOSE 8080

CMD ["python", "app.py"]
