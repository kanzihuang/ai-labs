#!/bin/bash
set -e
/app/decrypt-configs.sh
exec /app/curl-batch.sh "$@"
