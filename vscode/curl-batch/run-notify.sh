readonly NOTIFY_IMAGE='notify:latest'
readonly IMAGE_VERSION=${IMAGE##*:}

readonly DECRYPT_KEY=''
readonly NEXUS_USER=''
readonly NEXUS_PASSWORD=''

readonly NEXUS_REPOSITORY='release-version'
readonly NEXUS_DIRECTORY='java'
readonly NEXUS_NAME="${SERVICE}_${IMAGE_VERSION}.jar"


# imageVersion: 版本名称，取自镜像 ： 后的字符串，如：(devops-server:)20240327184229-6861-test-LY-SP1-1
readonly imageVersion=${targetImage##*:}

get_git_repositories() {
    (
        local codes="" #代码信息
        #此处处理拉取多仓库的情况，依此获取多仓库代码信息
        for i in REPONAME_{0..100}
        do
            codeRepo=${!i}
            if [ -z "$codeRepo" ]; then
                break #目录为空
            fi
            echo "获取仓库 $codeRepo 信息" >&2
            codePath="$WORKSPACE/$codeRepo"
            if [ ! -d "$codePath" ]; then
                echo "仓库 $codeRepo 目录不存在" >&2
                break
            fi
            cd "$codePath"
            # echo $(git log -1 --pretty=format:"%s")
            # commit_info=$(git log -1 --pretty=format:"%s"|sed 's/'"'"/ '/g'|sed 's/\"/ /g')
            #echo $commit_info
            repositoryUrl=$(git remote get-url origin)
            IFS='@' read -ra parts <<< "$repositoryUrl"
            repository=${parts[-1]}
            IFS='/' read -ra parts <<< "$repositoryUrl"
            repositoryName=${parts[-1]}
            branch=$(git branch -r | head -n 1)
            branch=$(echo "$branch" | sed 's/ //g')
            ci=$(git log -1 --pretty=format:"%s")
            ci=${ci//\"/}
            code='{
                "codeRepo":"'${repository}'",
                "codeRepoName":"'$repositoryName'",
                "branch":"'$branch'",
                "commitId":"'$(git log -1 --pretty=format:"%h")'",
                "commitInfo":"'$ci'",
                "commitUser":"'$(git log HEAD~1 --pretty=format:"%an" | head -n 1)'"
            }'
            if [ -z "$codes" ]; then
                codes="$code"
            else
                codes="$codes,$code"
            fi
        done

        echo $codes
    )
}

echo "----------------开始推送可执行文件-----------------"
rm -rf ./target/classes/
pName=$(find ./target -type f -name '*.jar' | head -n 1 | awk '{ print $1 }')
nexusName="${SERVICE}_${imageVersion}.jar" #二进制文件需要与镜像文件保持一致
curl --retry 3 -sS -u ${NEXUS_USER}:${NEXUS_PASSWORD} -X POST \
    -F raw.directory="/${NEXUS_DIRECTORY}/${SERVICE}" \
    -F raw.asset1="@${pName}" \
    -F raw.asset1.filename="${nexusName}" \
    'http://nexus.nancalcloud.com/service/rest/v1/components?repository=${NEXUS_REPOSITORY}'


echo "----------------开始推送制品通知-----------------"
docker run --rm --pull always \
    -e BUILD_OS="$(uname -s)" \
    -e BUILD_ARCH="$(uname -m)" \
    -e DECRYPT_KEY="$DECRYPT_KEY" \
    -e GIT_REPOSITORIES="$(get_git_repositories)" \
    -e NEXUS_DIRECTORY="$NEXUS_DIRECTORY" \
    -e NEXUS_NAME="$NEXUS_NAME" \
    -e NEXUS_REPOSITORY="$NEXUS_REPOSITORY" \
    -e SERVICE_NAME="$SERVICE" \
    -e TARGET_IMAGE="$IMAGE" \
    -e TASK_ID="$TASK_ID" \
    "$NOTIFY_IMAGE" || echo "制品通知发送失败"
