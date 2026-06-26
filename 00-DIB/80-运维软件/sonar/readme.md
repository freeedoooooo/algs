### 宿主机内核参数要求，SonarQube 依赖 Elasticsearch，启动前必须在宿主机执行
```
sudo sysctl -w vm.max_map_count=262144
```

### 永久生效需写入 /etc/sysctl.conf
```
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```