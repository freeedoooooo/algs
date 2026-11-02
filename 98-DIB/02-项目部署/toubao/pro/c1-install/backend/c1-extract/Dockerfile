# 基础镜像
FROM openjdk:8-jdk

# 维护者信息
LABEL maintainer="rui.hu@dibcn.com"

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装中文字体
# 方法1，容器内安装中文字体包
#RUN apt-get update && \
#    apt-get install -y fonts-wqy-microhei && \
#    rm -rf /var/lib/apt/lists/*
# 方法2，复制自定义字体文件到容器
# COPY ./custom-fonts/*.ttf /usr/share/fonts/
#方法3.将宿主机的字体目录挂载到容器中的 /usr/share/fonts 目录
VOLUME ["/usr/share/fonts"]

#更新字体缓存(如果复制了自定义字体文件)
RUN fc-cache -fv
#确认已安装字体清单
RUN fc-list :lang=zh

# 创建一个目录来存放 Spring Boot 应用的 JAR 文件
RUN mkdir /opt/app

# 将 Spring Boot 的 JAR 文件复制到容器中
COPY c1-extract.jar /opt/app/c1-extract.jar

# 设置工作目录
WORKDIR /opt/app

# 注：EXPOSE指令只是声明容器运行时提供的服务端口，给读者看有哪些端口
EXPOSE 30001

# 校验环境变量并启动 Spring Boot 应用
ENTRYPOINT ["sh", "-ec", \
    "if [ -z \"${C1_ENV}\" ]; then \
        echo 'Error: SPRING_PROFILES_ACTIVE must be set as an environment variable.'; \
        exit 1; \
    else \
        exec java -verbose:gc -Xloggc:/opt/app/logs/c1-extract.gc.log -XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xms6g -Xmx6g -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/opt/app/logs/c1-extract.heapdump.prof -Dspring.profiles.active=${C1_ENV} -jar /opt/app/c1-extract.jar; \
    fi"]

