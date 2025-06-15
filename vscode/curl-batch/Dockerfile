# 使用官方轻量级 Debian 镜像
FROM debian:stable-slim

# 安装 bash 和 curl
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash curl && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 拷贝当前目录所有内容到容器中
COPY . /app

# 赋予脚本可执行权限
RUN chmod +x curl-batch.sh

# 默认执行 bash，用户可自定义参数
ENTRYPOINT ["/app/curl-batch.sh"]
