/**
 * Jenkins Pipeline - 前端应用自动部署（纯环境变量配置）
 * todo 待精简，改为使用容器 jenkins-node20-builder
 *
 */
pipeline {
    agent any

    environment {
        // 服务器配置
        DEPLOY_SERVER = "www@10.0.5.70"
        DEPLOY_PATH = "/opt/www/c1-client"

        // 应用配置
        APP_NAME = "app-report"
        BUILD_OUTPUT = "app-report"
        TAR_NAME = "app-report.tar.gz"

        // Docker 构建配置
        NODE_IMAGE = "node:20.17.0-alpine"  // 使用 Alpine 版本（体积小 10 倍）
        NPM_REGISTRY = "http://maven.dibtime.com/repository/npm-public/"
        BUILD_COMMAND = "npm run build"

        // NPM 认证配置（访问私有包 dib-c1-components、dib-c1-check）
        NPM_AUTH_USER = "deployer"
        NPM_AUTH_PASS = "deployer123"

        // Git 配置
        GIT_URL = "http://gitlab.dibtime.com/dib-agent/dib-agent-app.git"
        GIT_BRANCH = "dev"
        GIT_CREDENTIALS_ID = "3123b10b-1c9a-4405-ad44-4b7ef1052783"

        // MinIO 配置
        SKIP_MINIO_UPLOAD = "true"              // true=跳过上传, false=上传到MinIO
        MINIO_URL = "http://10.0.5.178:9000"
        MINIO_USER = "c1_deploy"
        MINIO_SECRET = "dibwh123456"
        MINIO_ALIAS = "dib_minio"
        MINIO_LIB = "c1-deploy"                 // MinIO 存储桶名称
        DEPLOY_ENV = "pro-toubao"               // MinIO 部署环境

        // 构建优化配置
        ENABLE_FAST_BUILD = "true"          // true=启用快速构建（优先使用缓存）, false=总是完整构建

        // 动态变量
        TIMESTAMP = sh(script: 'date +"%Y%m%d%H%M%S"', returnStdout: true).trim()
    }

    stages {
        stage('环境检查') {
            steps {
                script {
                    echo "====== 部署信息 ======"
                    echo "应用名称: ${APP_NAME}"
                    echo "Git 仓库: ${GIT_URL}"
                    echo "Git 分支: ${GIT_BRANCH}"
                    echo "部署服务器: ${DEPLOY_SERVER}"
                    echo "部署路径: ${DEPLOY_PATH}"
                    echo "构建命令: ${BUILD_COMMAND}"
                    echo "时间戳: ${TIMESTAMP}"
                    echo ""
                    echo "MinIO 配置:"
                    echo "- 跳过上传: ${SKIP_MINIO_UPLOAD}"

                    if (env.SKIP_MINIO_UPLOAD == 'false') {
                        echo "- 部署环境: ${DEPLOY_ENV}"
                        echo "- MinIO 路径: ${MINIO_LIB}/${DEPLOY_ENV}/${APP_NAME}/"

                        // 生产环境需要确认
                        if (env.DEPLOY_ENV.contains('pro')) {
                            input message: '⚠️  确认上传到生产环境 MinIO？', ok: '确认上传'
                        }
                    }

                    echo "==================="
                }
            }
        }

        stage('拉取代码') {
            steps {
                checkout([
                        $class           : 'GitSCM',
                        branches         : [[name: "*/${GIT_BRANCH}"]],
                        userRemoteConfigs: [[
                                                    url          : "${GIT_URL}",
                                                    credentialsId: "${GIT_CREDENTIALS_ID}"
                                            ]]
                ])
            }
        }

        stage('准备 Docker 环境') {
            steps {
                script {
                    sh """
                        echo "====== 准备 Docker 环境 ======"
                        
                        # 检查镜像是否存在
                        if docker images ${NODE_IMAGE} | grep -q ${NODE_IMAGE}; then
                            echo "✅ 镜像已存在: ${NODE_IMAGE}"
                        else
                            echo "⚠️  镜像不存在，开始拉取: ${NODE_IMAGE}"
                            echo "⏳ Alpine 版本很小，预计 1-2 分钟..."
                            docker pull ${NODE_IMAGE}
                            echo "✅ 镜像拉取完成"
                        fi
                        
                        echo "====== 镜像信息 ======"
                        docker images ${NODE_IMAGE}
                    """

                    // 为每个构建任务创建唯一容器名称，避免并发争抢
                    def nodeVersion = env.NODE_IMAGE.replaceAll('[^0-9.]', '').split('\\.')[0]
                    env.BUILD_CONTAINER_NAME = "jenkins-node${nodeVersion}-${env.BUILD_TAG}"

                    echo "构建容器名称: ${env.BUILD_CONTAINER_NAME}"
                    echo "💡 使用独立容器，支持多任务并发执行"
                }
            }
        }

        stage('快速构建尝试') {
            when {
                expression { env.ENABLE_FAST_BUILD == 'true' }
            }
            steps {
                script {
                    env.FAST_BUILD_SUCCESS = 'false'

                    def fastBuildResult = sh(script: """
                        set +e  # 允许命令失败
                        
                        echo "====== 快速构建尝试（使用现有缓存）======"
                        
                        # 检查 node_modules 是否存在
                        if [ ! -d "${WORKSPACE}/node_modules" ]; then
                            echo "⚠️  node_modules 不存在，跳过快速构建"
                            exit 1
                        fi
                        
                        echo "✅ 发现 node_modules，尝试快速构建..."
                        
                        # 创建独立容器进行快速构建
                        echo "📦 创建构建容器: ${BUILD_CONTAINER_NAME}"
                        docker run -d \
                            --name ${BUILD_CONTAINER_NAME} \
                            --label "type=build" \
                            --label "build-tag=${BUILD_TAG}" \
                            -v "${WORKSPACE}:/workspace" \
                            -w /workspace \
                            ${NODE_IMAGE} tail -f /dev/null
                        
                        # 尝试直接构建
                        echo "🚀 尝试直接构建（不重新安装依赖）..."
                        docker exec \
                            -e HOME=/tmp \
                            -e NODE_OPTIONS="--max-old-space-size=4096" \
                            ${BUILD_CONTAINER_NAME} sh -c '
                                echo "====== 快速构建 ======" && 
                                ${BUILD_COMMAND} && 
                                echo "✅ 快速构建成功"
                            '
                        
                        BUILD_RESULT=\$?
                        
                        if [ \$BUILD_RESULT -eq 0 ]; then
                            echo "🎉 快速构建成功！跳过完整构建阶段"
                            exit 0
                        else
                            echo "⚠️  快速构建失败，将执行完整构建"
                            # 清理失败的容器
                            docker stop ${BUILD_CONTAINER_NAME} 2>/dev/null || true
                            docker rm ${BUILD_CONTAINER_NAME} 2>/dev/null || true
                            exit 1
                        fi
                    """, returnStatus: true)

                    // 检查快速构建是否成功
                    if (fastBuildResult == 0) {
                        env.FAST_BUILD_SUCCESS = 'true'
                        echo "✅ 快速构建成功，将跳过完整构建"
                    } else {
                        env.FAST_BUILD_SUCCESS = 'false'
                        echo "⚠️  快速构建失败，将执行完整构建"
                    }
                }
            }
        }

        stage('完整构建') {
            when {
                expression {
                    env.ENABLE_FAST_BUILD == 'false' || env.FAST_BUILD_SUCCESS == 'false'
                }
            }
            steps {
                script {
                    sh """
                        set -e
                        
                        echo "====== 执行完整构建 ======"
                        
                        # 清理旧的构建产物和缓存
                        echo "清理 node_modules 和锁文件..."
                        rm -rf ${WORKSPACE}/node_modules || true
                        rm -f ${WORKSPACE}/package-lock.json || true
                        
                        echo "清理 npm 缓存目录..."
                        rm -rf ${WORKSPACE}/.npm || true
                        rm -rf /tmp/.npm* || true
                        
                        echo "✅ 缓存清理完成"
                        
                        # 创建构建容器（如果快速构建失败，容器已被清理）
                        if ! docker ps -a --format '{{.Names}}' | grep -q "^${BUILD_CONTAINER_NAME}\$"; then
                            echo "📦 创建构建容器: ${BUILD_CONTAINER_NAME}"
                            docker run -d \
                                --name ${BUILD_CONTAINER_NAME} \
                                --label "type=build" \
                                --label "build-tag=${BUILD_TAG}" \
                                -v "${WORKSPACE}:/workspace" \
                                -w /workspace \
                                ${NODE_IMAGE} tail -f /dev/null
                        fi
                        
                        # 执行完整构建流程
                        echo "🚀 开始完整构建..."
                        docker exec \
                            -e HOME=/tmp \
                            -e NODE_OPTIONS="--max-old-space-size=4096" \
                            -e NPM_REGISTRY="${NPM_REGISTRY}" \
                            -e NPM_AUTH_USER="${NPM_AUTH_USER}" \
                            -e NPM_AUTH_PASS="${NPM_AUTH_PASS}" \
                            -e BUILD_COMMAND="${BUILD_COMMAND}" \
                            ${BUILD_CONTAINER_NAME} sh -c '
                                echo "====== 清理缓存和配置 ======" && 
                                
                                # 1. 彻底清理 npm 缓存
                                echo "清理 npm 缓存..." && 
                                npm cache clean --force && 
                                npm cache verify && 
                                
                                # 2. 配置 npm 源和重试策略
                                echo "配置 NPM 私有源..." && 
                                npm config set registry \${NPM_REGISTRY} && 
                                npm config set fetch-retries 5 && 
                                npm config set fetch-retry-mintimeout 20000 && 
                                npm config set fetch-retry-maxtimeout 120000 && 
                                
                                # 3. 配置私有包认证（Base64 Token）
                                echo "配置私有包认证..." && 
                                AUTH_TOKEN=\$(echo -n "\${NPM_AUTH_USER}:\${NPM_AUTH_PASS}" | base64) && 
                                npm config set "//maven.dibtime.com/:_auth" "\${AUTH_TOKEN}" && 
                                
                                echo "验证 npm 配置..." && 
                                npm config list && 
                                
                                echo "====== 开始安装依赖 ======" && 
                                # 4. 安装依赖
                                npm install --prefer-online --no-fund --no-audit --loglevel=verbose && 
                                
                                echo "====== 开始构建 ======" && 
                                # 5. 构建项目
                                \${BUILD_COMMAND} && 
                                
                                echo "✅ 完整构建完成"
                            '
                        
                        echo "====== 构建完成 ======"
                        echo "检查构建产物:"
                        ls -lah ${BUILD_OUTPUT}/
                    """
                }
            }
        }

        stage('清理构建容器') {
            steps {
                sh """
                    echo "====== 清理构建容器 ======"
                    
                    # 清理构建容器
                    if docker ps -a --format '{{.Names}}' | grep -q "^${BUILD_CONTAINER_NAME}\$"; then
                        echo "🧹 清理容器: ${BUILD_CONTAINER_NAME}"
                        docker stop ${BUILD_CONTAINER_NAME} 2>/dev/null || true
                        docker rm ${BUILD_CONTAINER_NAME} 2>/dev/null || true
                        echo "✅ 容器已清理"
                    else
                        echo "⚠️  容器不存在，跳过清理"
                    fi
                """
            }
        }

        stage('打包构建产物') {
            steps {
                sh """
                    set -e
                    
                    echo "====== 打包构建产物 ======"
                    
                    # 使用 tar 打包构建产物，排除 vite 临时文件
                    tar -czf ${TAR_NAME} --exclude='vite.config.js.timestamp-*' ${BUILD_OUTPUT}
                    
                    echo "检查打包文件:"
                    ls -lh ${TAR_NAME}
                    
                    echo "====== 打包完成 ======"
                """
            }
        }

        stage('上传到 MinIO') {
            when {
                expression { env.SKIP_MINIO_UPLOAD == 'false' }
            }
            steps {
                script {
                    echo "====== 上传到 MinIO ======"
                    echo "目标环境: ${env.DEPLOY_ENV}"
                    echo "MinIO 路径: ${env.MINIO_LIB}/${env.DEPLOY_ENV}/${env.APP_NAME}/${env.TAR_NAME}"

                    // 使用凭证管理（推荐方式，更安全）
                    withCredentials([usernamePassword(
                            credentialsId: 'c1_deploy',
                            usernameVariable: 'MINIO_ACCESS_KEY',
                            passwordVariable: 'MINIO_SECRET_KEY'
                    )]) {
                        sh """
                            set -e
                            
                            echo "配置 MinIO 客户端..."
                            mc alias set ${MINIO_ALIAS} ${MINIO_URL} \${MINIO_ACCESS_KEY} \${MINIO_SECRET_KEY}
                            
                            echo "上传构建产物到 MinIO..."
                            mc put ${WORKSPACE}/${TAR_NAME} ${MINIO_ALIAS}/${MINIO_LIB}/${DEPLOY_ENV}/${APP_NAME}/${TAR_NAME}
                            
                            echo "✅ MinIO 上传完成"
                            echo "访问路径: ${MINIO_ALIAS}/${MINIO_LIB}/${DEPLOY_ENV}/${APP_NAME}/${TAR_NAME}"
                        """
                    }
                }
            }
        }
        stage('部署到目标服务器') {
            steps {
                sh """
                    set -e
                    
                    echo "====== 开始部署到 ${DEPLOY_SERVER} ======"
                    
                    echo "1. 备份旧应用..."
                    ssh ${DEPLOY_SERVER} "
                        if [ -d ${DEPLOY_PATH}/${BUILD_OUTPUT} ]; then
                            echo '发现旧版本，创建备份...'
                            mv ${DEPLOY_PATH}/${BUILD_OUTPUT} ${DEPLOY_PATH}/${BUILD_OUTPUT}.backup.${TIMESTAMP} || true
                        fi
                    "
                    
                    echo "2. 传输构建产物到目标服务器..."
                    scp ${WORKSPACE}/${TAR_NAME} ${DEPLOY_SERVER}:${DEPLOY_PATH}/
                    
                    echo "3. 在目标服务器解压..."
                    ssh ${DEPLOY_SERVER} "
                        cd ${DEPLOY_PATH} && 
                        tar -xzf ${TAR_NAME} &&
                        rm -f ${TAR_NAME}
                    "
                    
                    echo "4. 验证部署..."
                    ssh ${DEPLOY_SERVER} "ls -lah ${DEPLOY_PATH}/${BUILD_OUTPUT}"
                    
                    echo "5. 清理旧备份（保留最近1个）..."
                    ssh ${DEPLOY_SERVER} "
                        cd ${DEPLOY_PATH} &&
                        ls -dt ${BUILD_OUTPUT}.backup.* 2>/dev/null | tail -n +2 | xargs rm -rf {} 2>/dev/null || true
                    "
                    
                    echo "====== 部署完成 ======"
                """
            }
        }
    }

    post {
        success {
            script {
                def duration = currentBuild.durationString.replace(' and counting', '')
                def minioStatus = env.SKIP_MINIO_UPLOAD == 'true' ? "跳过" : "已上传到 ${env.MINIO_LIB}/${env.DEPLOY_ENV}/${env.APP_NAME}/"
                def buildMode = env.FAST_BUILD_SUCCESS == 'true' ? "快速构建（使用缓存）⚡" : "完整构建"

                echo """
                ====================================
                ✅ 部署成功
                ====================================
                应用名称: ${APP_NAME}
                Git 分支: ${GIT_BRANCH}
                构建模式: ${buildMode}
                MinIO 状态: ${minioStatus}
                构建时间: ${duration}
                时间戳: ${TIMESTAMP}
                部署服务器: ${DEPLOY_SERVER}
                ====================================
                """

                // 可以在这里添加钉钉/企业微信通知
                // dingTalk robot: 'xxx', message: "✅ ${APP_NAME} 部署成功"
            }
        }

        failure {
            script {
                def minioStatus = env.SKIP_MINIO_UPLOAD == 'true' ? "跳过" : env.DEPLOY_ENV

                echo """
                ====================================
                ❌ 部署失败
                ====================================
                应用名称: ${APP_NAME}
                Git 分支: ${GIT_BRANCH}
                MinIO 环境: ${minioStatus}
                请检查构建日志
                ====================================
                """

                // 可以在这里添加钉钉/企业微信通知
                // dingTalk robot: 'xxx', message: "❌ ${APP_NAME} 部署失败，请检查"
            }
        }

        always {
            script {
                // 确保清理操作总是执行
                sh """
                    echo "执行最终清理..."
                    
                    # 清理构建文件
                    rm -f ${WORKSPACE}/${TAR_NAME} 2>/dev/null || true
                    
                    # 保留 node_modules 用于下次快速构建（如果启用快速构建）
                    if [ "${ENABLE_FAST_BUILD}" = "false" ]; then
                        echo "快速构建已禁用，清理 node_modules..."
                        rm -rf ${WORKSPACE}/node_modules 2>/dev/null || true
                    else
                        echo "快速构建已启用，保留 node_modules 用于下次构建"
                    fi
                    
                    # 清理可能残留的构建容器
                    if [ -n "${BUILD_CONTAINER_NAME}" ]; then
                        if docker ps -a --format '{{.Names}}' | grep -q "^${BUILD_CONTAINER_NAME}\$"; then
                            echo "🧹 清理残留的构建容器: ${BUILD_CONTAINER_NAME}"
                            docker stop ${BUILD_CONTAINER_NAME} 2>/dev/null || true
                            docker rm ${BUILD_CONTAINER_NAME} 2>/dev/null || true
                        fi
                    fi
                    
                    echo "✅ 最终清理完成"
                """

                // 归档构建产物（可选）
                // archiveArtifacts artifacts: "${TAR_NAME}", fingerprint: true, allowEmptyArchive: true
            }
        }
    }
}

