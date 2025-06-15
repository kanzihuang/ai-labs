# 使用官方轻量级 Debian 镜像
FROM debian:stable-slim

# 安装 bash、curl、openssl、ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash \
        curl \
        openssl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 只拷贝加密后的配置和脚本
COPY conf_encrypted/ conf_encrypted/
COPY curl-batch.sh decrypt-configs.sh entrypoint.sh .

RUN chmod +x curl-batch.sh decrypt-configs.sh entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
