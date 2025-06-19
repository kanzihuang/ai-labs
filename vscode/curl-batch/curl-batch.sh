#!/bin/bash

# buildOS: 系统名称，linux
readonly buildOS="$BUILD_OS"
# buildArch: 系统架构，x86
readonly buildArch="$BUILD_ARCH"
# gitRepositories: json对象，代码创建信息
readonly gitRepositories="$GIT_REPOSITORIES"
# imagePull: 镜像拉取命令
readonly imagePull="docker pull '$TARGET_IMAGE'"
# imageVersion: 版本名称，取自镜像 ： 后的字符串，如：(devops-server:)20240327184229-6861-test-LY-SP1-1
readonly imageVersion=${TARGET_IMAGE##*:}
# serviceName: 服务名
readonly serviceName="$SERVICE_NAME"
# targetImage: 镜像名，如：devops-server:20240327184229-6861-test-LY-SP1-1
readonly targetImage="$TARGET_IMAGE"
# taskID: 构建任务id
readonly taskID="$TASK_ID"
# nexusName: 二进制文件名，java的.jar,vue的.tgz，名称，不是路径
readonly nexusName="$NEXUS_NAME"
# nexusUrl: 二进制文件下载地址
readonly nexusUrl="https://nexus.nancalcloud.com/repository/$NEXUS_REPOSITORY/$NEXUS_DIRECTORY/$SERVICE_NAME/${nexusName}"

DRY_RUN=0

curl_cmd() {
    local conf_file="$1"
    if [[ ! -f "$conf_file" ]]; then
        echo "Config file '$conf_file' not found: $conf_file" >&2
        exit 1
    fi

    local requestUrl requestHeaders requestBody
    source "$conf_file"
    if [ $? -ne 0 ]; then
        echo "source '$conf_file' failed" >&2
        exit 1
    fi

    echo "notifying '${requestUrl}' with body '${requestBody}'" >&2
    if [[ $DRY_RUN -eq 0 ]]; then
        curl -H "Content-Type: application/json" --retry 3 -sS -X POST \
            "${requestHeaders[@]}" \
            -d "${requestBody}" \
            "${requestUrl}"
        if [ $? -ne 0 ]; then
            echo -e "构建通知发送失败" >&2
        fi
        echo
        return 0
    fi
}

main() {
    # 配置目录改为解密后的 conf_decrypted
    local config_dir="$(cd "$(dirname "$0")/conf_decrypted" && pwd)"
    local sites=()
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

    local site file
    if [[ ${#sites[@]} -gt 0 ]]; then
        for site in "${sites[@]}"; do
            curl_cmd "$config_dir/$site.sh"
        done
    else
        for file in $config_dir/*.sh; do
            curl_cmd $file
        done
    fi
}

main "$@"
