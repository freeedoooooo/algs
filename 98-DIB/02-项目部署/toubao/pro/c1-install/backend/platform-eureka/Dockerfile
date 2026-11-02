# 基础镜像
FROM openjdk:8-jdk

# 维护者信息
LABEL maintainer="rui.hu@dibcn.com"

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 创建一个目录来存放 Spring Boot 应用的 JAR 文件
RUN mkdir /opt/app

# 将 Spring Boot 的 JAR 文件复制到容器中
COPY platform-eureka.jar /opt/app/platform-eureka.jar

# 设置工作目录
WORKDIR /opt/app

# 注：EXPOSE指令只是声明容器运行时提供的服务端口，给读者看有哪些端口
EXPOSE 10000

# 校验环境变量并启动 Spring Boot 应用
ENTRYPOINT ["sh", "-ec", \
    "if [ -z \"${C1_ENV}\" ]; then \
        echo 'Error: SPRING_PROFILES_ACTIVE must be set as an environment variable.'; \
        exit 1; \
    else \
        exec java -Xms512m -Xmx2048m -Dspring.profiles.active=${C1_ENV} -jar /opt/app/platform-eureka.jar; \
    fi"]

