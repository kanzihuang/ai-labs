#!/bin/bash

curl() {
    command curl -I "$url"
}

main() {
    config_dir="$(cd "$(dirname "$0")/conf" && pwd)"
    sites=()
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
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
            file="$config_dir/$site.curl"
            if [[ ! -f "$file" ]]; then
                echo "Config file for site '$site' not found: $file" >&2
                exit 1
            fi
            source "$file"
            curl
        done
    else
        for file in $config_dir/*.curl; do
            if [[ ! -f "$file" ]]; then
                echo "$file is not a config file."
                exit 1
            fi
            source "$file"
            curl
        done
    fi
}

main "$@"
