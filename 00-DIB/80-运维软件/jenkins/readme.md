# 前端打包说明

```
# 复用node构建容器 jenkins-node20-builder，只区分目录
docker exec jenkins-node20-builder sh -c "cd ./dev-c1/app-report && npm cache clean --force"
docker exec jenkins-node20-builder sh -c "cd ./dev-c1/app-report && npm cache verify"
docker exec jenkins-node20-builder sh -c "cd ./dev-c1/app-report && npm install --prefer-online --no-fund --no-audit --loglevel=verbose"
docker exec jenkins-node20-builder sh -c "cd ./dev-c1/app-report && npm run build"
```