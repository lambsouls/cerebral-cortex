# 基于更小的镜像
FROM python:3.10-alpine

ENV PYTHONPATH=/app

# 容器元数据
LABEL org.opencontainers.image.title="Cerebral Cortex"
LABEL org.opencontainers.image.description="LLM API Gateway Middleware"

WORKDIR /app

# 优化依赖安装顺序
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 添加安全用户
RUN adduser -D cortexuser && \
    chown -R cortexuser:cortexuser /app

COPY ./app ./app
COPY ./mods ./mods

USER cortexuser  # 非root运行

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
