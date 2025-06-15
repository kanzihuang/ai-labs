#!/bin/bash

curl() {
    command curl -I "$url"
}

main() {
    config_dir="$(cd "$(dirname "$0")/conf" && pwd)"

    for file in $config_dir/*.curl; do
        if [[ ! -f "$file" ]]; then
            echo "$file is not a config file."
            exit 1
        fi
        source "$file"
        curl
    done
}

main "$@"
