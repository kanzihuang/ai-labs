#!/bin/bash

readonly serviceName="$SERVICE"
readonly imageTarget="$IMAGE"
readonly taskID="$TASK_ID"
readonly nexusPrefix="$NEXUS_PREFIX"
readonly gitRepositories="$GIT_REPOSITORIES"
readonly buildOS="$BUILD_OS"
readonly buildArch="$BUILD_ARCH"

readonly imagePull="docker pull '$imageTarget'"
readonly imageVersion=${imageTarget##*:}
readonly nexusName="${serviceName}_${imageVersion}.jar"
readonly nexusUrl="$nexusPrefix/${nexusName}"

DRY_RUN=0

curl_cmd() {
    # local cmd='curl --retry 3 -X POST -H '"'"'Content-Type: application/json'"'"' -H '"'"'AccessKeyId: '$accessKeyId"'"' -H '"'"'AccessKeySecret: '$accessKeySecret"'"' -d '"'"$requestBody"'"' '"'"$requestUrl"'"
    local cmd=$(cat <<EOF
        curl --retry 3 \
            -X POST \
            -H "Content-Type: application/json" \
            ${requestHeaders} \
            -d '${requestBody}' \
            '${requestUrl}'
EOF
    )
    echo "$cmd"
    if [[ $DRY_RUN -eq 0 ]]; then
        eval $cmd
    fi
}

main() {
    # 配置目录改为解密后的 conf_decrypted
    config_dir="$(cd "$(dirname "$0")/conf_decrypted" && pwd)"
    sites=()
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --site)
                if [[ -n "$2" && "$2" != --* ]]; then
                    sites+=("$2")
                    shift 2
                else
                    echo "Error: --site requires a value." >&2
                    exit 1
                fi
                ;;
            --site=*)
                site_value="${1#--site=}"
                if [[ -n "$site_value" ]]; then
                    sites+=("$site_value")
                    shift
                else
                    echo "Error: --site= requires a value." >&2
                    exit 1
                fi
                ;;
            *)
                shift
                ;;
        esac
    done

    if [[ ${#sites[@]} -gt 0 ]]; then
        for site in "${sites[@]}"; do
            file="$config_dir/$site.sh"
            if [[ ! -f "$file" ]]; then
                echo "Config file for site '$site' not found: $file" >&2
                exit 1
            fi
            source "$file"
            curl_cmd
        done
    else
        for file in $config_dir/*.sh; do
            if [[ ! -f "$file" ]]; then
                echo "$file is not a config file."
                exit 1
            fi
            source "$file"
            curl_cmd
        done
    fi
}

main "$@"
