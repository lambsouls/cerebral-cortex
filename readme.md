启动容器集群
docker-compose up -d --build

查看运行状态
docker ps --filter "name=cerebral-cortex"

验证模块加载 查看容器日志：
docker logs cerebral-cortex
