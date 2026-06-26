# ollama 安装说明

### 版本说明

```
ollama=v0.12.9
```

### 使用 docker-compose 安装

```
cd /opt/app/ollama
docker compose up -d
```

### 验证安装

```
docker exec ollama ollama --version
```

### 下载，并运行模型

```
docker exec -it ollama /bin/bash

# 下载并运行模型
ollama run qwen3:1.7b

# 退出
/bye
```

### 接口验证

```
ollama list

http://10.0.5.174:11434/api/generate
{
  "model": "qwen3:1.7b",
  "prompt": "1+1=?",
  "stream": false
}
```

### 使用 Cherry Studio 聊天验证

```
# 接口地址配置
http://10.0.5.174:11434
```