# 基础镜像
FROM openjdk:8-jdk

# 维护者信息
LABEL maintainer="zikang.xiong@dibcn.com"

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装中文字体
# 使用阿里云的 Debian 镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# 安装字体管理工具
# extract和mdm容器，安装 unoconv（专门用于 wps 文档转换）
ARG CONTAINER_NAME
RUN apt-get update && \
    if [ "${CONTAINER_NAME}" = "dib-agent-service-extract-web" ] || [ "${CONTAINER_NAME}" = "data-cloud-mdm" ]; then \
        apt-get install -y unoconv libreoffice-core libreoffice-common fontconfig && rm -rf /var/lib/apt/lists/*; \
    else \
        apt-get install -y fontconfig && rm -rf /var/lib/apt/lists/*; \
    fi

# 方法1，容器内安装中文字体包
# RUN apt-get update && \
#     apt-get install -y fonts-wqy-microhei && \
#     rm -rf /var/lib/apt/lists/*
# 方法2，复制自定义字体文件到容器
# COPY ./custom-fonts/*.ttf /usr/share/fonts/
# 方法3. 将宿主机的字体目录挂载到容器中的 /usr/share/fonts 目录
VOLUME ["/usr/share/fonts"]
# 更新字体缓存（如果复制了自定义字体文件）
RUN fc-cache -fv
# 确认已安装字体清单
RUN fc-list :lang=zh

# 设置默认用户
ARG USER=c1
# 创建 用户 和 home目录
RUN useradd -m ${USER}
# 创建应用目录，并设置权限
RUN mkdir -p /opt/app && chown ${USER}:${USER} /opt/app

# 设置工作目录
WORKDIR /opt/app

# 将 Spring Boot 的 JAR 文件复制到容器中
ARG LOCAL_JAR_FILE

# 检查参数是否为空
RUN if [ -z "${LOCAL_JAR_FILE}" ]; then echo "Error: LOCAL_JAR_FILE is not set"; exit 1; fi
RUN if [ -z "${CONTAINER_NAME}" ]; then echo "Error: CONTAINER_NAME is not set"; exit 1; fi
COPY --chown=${USER}:${USER} ${LOCAL_JAR_FILE} /opt/app/${CONTAINER_NAME}.jar


# 暴露 Spring Boot 应用的端口（根据实际情况修改）， 默认值为 29204
# ARG SERVICE_PORT=29204
# EXPOSE ${SERVICE_PORT}


# 切换用户
USER ${USER}

# 校验环境变量并启动 Spring Boot 应用
# docker build -t dib-spring-boot-rule .
# docker run -d -e SPRING_PROFILES_ACTIVE=dev -p 1234:9204 --name my-spring-boot-rule dib-spring-boot-rule
# 校验环境变量并启动 Spring Boot 应用
ENTRYPOINT ["sh", "-ec", \
    "if [ -z \"${SPRING_PROFILES_ACTIVE}\" ]; then \
        echo 'Error: SPRING_PROFILES_ACTIVE must be set as an environment variable'; \
        exit 1; \
    elif [ -z \"${JAR_FILE_NAME}\" ]; then \
        echo 'Error: JAR_FILE_NAME must be set as an environment variable'; \
        exit 1; \
    elif [ ! -f \"/opt/app/${JAR_FILE_NAME}\" ]; then \
        echo 'Error: JAR file ${JAR_FILE_NAME} not found in /opt/app/'; \
        exit 1; \
    else \
        exec java -Xms1024m -Xmx4096m -Dspring.profiles.active=${SPRING_PROFILES_ACTIVE} -jar /opt/app/${JAR_FILE_NAME}; \
    fi"]

