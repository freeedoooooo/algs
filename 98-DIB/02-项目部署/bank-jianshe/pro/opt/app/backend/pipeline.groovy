// ##########################
// # Jenkins Pipeline 示例 #
// #########################
pipeline {
    agent any

    environment {
        // 部署的目标服务器IP
        DEPLOY_SERVER_IP = "192.168.10.141"
        DEPLOY_SCRIPT = "/opt/app/backend/update.sh"

        // 原服务名及jar路径
        SOURCE_APP_NAME = "dib-agent-service-extract-web"
        LOCAL_JAR_PATH = "./${SOURCE_APP_NAME}/target/${SOURCE_APP_NAME}*-exec.jar"

        // 启动环境变量
        C1_ENV = "jianshe-pro"
        // 统一服务别名
        TARGET_APP_NAME = "c1-extract"

        // gitlab配置
        GIT_URL = "http://gitlab.dibtime.com/dib-agent/dib-agent-service-extract.git"
        GIT_BRANCH = "master-bank-jianshe"
        GIT_CREDENTIALSID = "gitlab"

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
                        credentialsId: GIT_CREDENTIALSID
                )
            }
        }

        stage('maven package') {
            steps {
                sh "mvn clean package -Dmaven.test.skip=true"
                echo "maven 打包完成"
            }
        }

        stage('minio upload') {
            steps {
                sh """
                    set -e
                    
                    # 配置 MinIO 别名
                    mc alias set dib_minio ${MINIO_URL} ${MINIO_USER} ${MINIO_SECRET}
                    
                    echo "开始上传文件到 minio..."
                    mc put ${LOCAL_JAR_PATH}  dib_minio/c1-deploy/${C1_ENV}/${TARGET_APP_NAME}/${TARGET_APP_NAME}.jar
                    echo "minio 文件上传完成"
                """
            }
        }

        stage('docker restart') {
            steps {
                sh """
                    set -e
                    
                    echo "通过SSH执行远程脚本update.sh..."
                    ssh root@${DEPLOY_SERVER_IP} "bash ${DEPLOY_SCRIPT} ${TARGET_APP_NAME} "
                    echo "docker 更新完成"
                """
            }
        }

    }
}