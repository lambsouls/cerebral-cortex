cerebral-cortex/
├── .env                 # 环境变量文件
├── docker-compose.yml
├── Dockerfile
├── mods/               # 动态模块
│   ├── 01_logger.py    # 编号控制执行顺序
│   └── 90_safety.py
└── app/
    ├── __init__.py
    ├── main.py
    ├── mod_loader.py
    └── models.py

启动容器集群
docker-compose up -d --build

查看运行状态
docker ps --filter "name=cerebral-cortex"

验证模块加载 查看容器日志：
docker logs cerebral-cortex