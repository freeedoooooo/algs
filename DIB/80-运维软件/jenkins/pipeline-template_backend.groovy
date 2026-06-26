pipeline {
    agent any

    environment {
        // 显式指定使用 Jenkins 工具中配置的 JDK。替换为你在 Jenkins > Global Tool Configuration 中设置的名称
        JAVA_HOME = tool 'JDK8'
        MAVEN_HOME = tool 'maven-3.8.1'
        PATH = "${JAVA_HOME}/bin:${MAVEN_HOME}/bin:${env.PATH}"

        // 部署的目标服务器IP
        DEPLOY_SERVER_IP = "10.0.6.183"
        DEPLOY_DOCKER_COMPOSE_PATH = "/opt/app/c1/docker-compose.yml"
        // 启动环境变量
        C1_ENV = "idc-test-tb"

        // gitlab配置
        GIT_URL = "http://gitlab.dibtime.com/dib-agent/dib-agent-service-data.git"
        GIT_BRANCH = "dev-tb"
        GIT_credentialsId = "3123b10b-1c9a-4405-ad44-4b7ef1052783"

        // 原服务名及jar路径
        SERVICE_NAME = "dib-agent-service-data-web"
        LOCAL_JAR_PATH = "./${SERVICE_NAME}/target/${SERVICE_NAME}*-exec.jar"
        // 统一服务别名
        ALIAS_NAME = "c1-data"

        // dockerhub配置
        REGISTRY_URL = "10.0.6.183:8088"
        DOCKER_USER = "robot\\\$dibot"
        DOCKER_SECRET = "3zVGFfk3hNSP2y39I00Cr2t2WKvh7W5l"

        // 镜像名
        TIMESTAMP = sh(script: 'date +"%Y%m%d-%H%M"', returnStdout: true).trim()
        VERSION_TAG = "${C1_ENV}_${TIMESTAMP}"
        IMAGE_NAME_TIMESTAMP = "${REGISTRY_URL}/c1/${ALIAS_NAME}:${VERSION_TAG}"
        IMAGE_NAME_LATEST = "${REGISTRY_URL}/c1/${ALIAS_NAME}:${C1_ENV}_latest"

        // minio配置
        MINIO_URL = "http://10.0.5.178:9000"
        MINIO_USER = "c1_deploy"
        MINIO_SECRET = "dibwh123456"
    }

    stages {
        stage('git pull') {
            steps {
                git(
                        branch: GIT_BRANCH,
                        url: GIT_URL,
                        credentialsId: GIT_credentialsId
                )
            }
        }

        stage('maven package') {
            steps {
                sh "mvn clean package -Dmaven.test.skip=true"
                echo "maven 打包完成"
            }
        }

        stage('mv jar') {
            steps {
                echo "移动 jar 到目录 ./docker"
                sh "mv ${LOCAL_JAR_PATH}  ./docker/${ALIAS_NAME}.jar"
            }
        }

        stage('docker build') {
            steps {
                sh """
                    set -e
                    
                    cd ./docker

                    echo "开始构建 Docker 镜像..."
                    docker build -t "${IMAGE_NAME_TIMESTAMP}" -t "${IMAGE_NAME_LATEST}" .
                    echo "docker 镜像构建完成"
                """
            }
        }

        stage('docker push') {
            steps {
                sh """
                    set -e
                    
                    # 登录 Registry
                    echo "登录 Docker Registry..."
                    docker login -u ${DOCKER_USER} -p "${DOCKER_SECRET}" "${REGISTRY_URL}"
                
                    echo "开始推送 Docker 镜像..."
                    docker push "${IMAGE_NAME_TIMESTAMP}"
                    docker push "${IMAGE_NAME_LATEST}"
                    echo "docker 镜像推送完成"
                """
            }
        }

        stage('minio upload') {
            steps {
                sh """
                    set -e

                    cd ./docker
                    
                    # 配置 MinIO 别名
                    mc alias set dib_minio ${MINIO_URL} ${MINIO_USER} ${MINIO_SECRET}
                    
                    echo "开始上传文件到 minio..."
                    mc put ./*.jar  dib_minio/c1-deploy/${C1_ENV}/${ALIAS_NAME}/${ALIAS_NAME}.jar
                    mc put ./Dockerfile  dib_minio/c1-deploy/${C1_ENV}/${ALIAS_NAME}/Dockerfile
                    echo "minio 文件上传完成"
                """
            }
        }

        stage('docker restart') {
            steps {
                sh """
                    set -e
                    
                    echo "远程执行 docker compose up..."
                    ssh -t www@"${DEPLOY_SERVER_IP}" C1_ENV="${C1_ENV}" C1_VERSION="${VERSION_TAG}" docker compose -f ${DEPLOY_DOCKER_COMPOSE_PATH} up -d ${ALIAS_NAME}
                    echo "docker 更新完成"
                """
            }
        }

    }
}