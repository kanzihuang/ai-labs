DECRYPT_KEY=''
NOTIFY_IMAGE='notify:latest'
NEXUS_REPOSITORY='release-version'
NEXUS_DIRECTORY='java'

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
            echo "获取仓库 $codeRepo 信息"
            codePath="$WORKSPACE/$codeRepo"
            if [ ! -d "$codePath" ]; then
                echo "仓库 $codeRepo 目录不存在"
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

#发送制品通知
docker run --rm --pull always \
    -e DECRYPT_KEY=“$DECRYPT_KEY” \
    -e SERVICE_NAME="$SERVICE" \
    -e TARGET_IMAGE="$IMAGE" \
    -e TASK_ID="$TASK_ID" \
    -e NEXUS_DIRECTORY="$NEXUS_DIRECTORY" \
    -e NEXUS_REPOSITORY="$NEXUS_REPOSITORY" \
    -e BUILD_OS="$(uname -s)" \
    -e BUILD_ARCH="$(uname -m)" \
    -e GIT_REPOSITORIES="$(get_git_repositories)" \
    "$NOTIFY_IMAGE" || echo "制品通知发送失败"
