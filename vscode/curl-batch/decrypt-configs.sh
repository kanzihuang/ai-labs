#!/bin/bash
set -e

# 解密 conf_encrypted/*.curl.enc 到 conf_decrypted/*.curl
# 需要环境变量 DECRYPT_KEY

if [[ -z "$DECRYPT_KEY" ]]; then
  echo "Error: DECRYPT_KEY 环境变量未设置，无法解密配置文件。" >&2
  exit 1
fi

mkdir -p conf_decrypted
for encfile in conf_encrypted/*.curl.enc; do
  base=$(basename "$encfile" .enc)
  openssl enc -d -aes-256-cbc -pbkdf2 -in "$encfile" -out "conf_decrypted/$base" -k "$DECRYPT_KEY"
done
