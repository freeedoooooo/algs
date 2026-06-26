FROM hub.dibtime.com/public/openjdk:17-ea-33-slim-buster

# 使用 Debian 官方归档源（适用于已 EOL 的版本）
RUN echo "deb http://archive.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian-security buster/updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian buster-updates main contrib non-free" >> /etc/apt/sources.list

# 禁用 apt 的 Release 文件校验
RUN echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until

# 安装工具 + LibreOffice
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    wget \
    curl \
    vim \
    nano \
    telnet \
    iputils-ping \
    net-tools \
    dnsutils \
    iproute2 \
    tcpdump \
    iotop \
    htop \
    fontconfig \
    ttf-wqy-zenhei \
    ttf-wqy-microhei \
    unoconv \
    locales \
    # LibreOffice 及其必要依赖（支持 headless 文档转换）
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    libreoffice-draw \
    libreoffice-math \
    libreoffice-core \
    libreoffice-common \
    fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置时区为东八区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 启用中文
RUN sed -i 's/^# *\(zh_CN.UTF-8\)/\1/' /etc/locale.gen && locale-gen
ENV LANG=zh_CN.UTF-8
ENV LANGUAGE=zh:cn
ENV LC_ALL=zh_CN.UTF-8

# 刷新字体缓存（确保中文字体生效）
RUN fc-cache -fv

# 验证 LibreOffice 是否可用（可选，用于调试）
# RUN libreoffice --version

ENTRYPOINT ["/bin/bash"]
