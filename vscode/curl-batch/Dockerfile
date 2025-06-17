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
COPY curl-batch.sh decrypt-configs.sh entrypoint.sh ./

ARG user=curl
ARG group=curl
ARG uid=1000
ARG gid=1000
ARG CONF_DECRYPTED=/app/conf_decrypted

RUN groupadd -g ${gid} ${group} \
  && useradd -u ${uid} -g ${gid} -l -m -s /bin/bash ${user} \
  && chmod +x curl-batch.sh decrypt-configs.sh entrypoint.sh \
  && mkdir -p $CONF_DECRYPTED \
  && chown ${gid}:${uid} $CONF_DECRYPTED

USER ${user}

ENTRYPOINT ["/app/entrypoint.sh"]
