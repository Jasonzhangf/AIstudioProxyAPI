# 多账号路由池管理器使用指南

## 概述

多账号路由池管理器允许你同时运行多个 AI Studio 账号实例，并通过统一入口进行访问。系统会自动将请求分发到不同的账号实例，实现负载均衡和故障转移。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     统一入口 (端口 8080)                      │
│                     multi_account_router.py                   │
└─────────────────────────────────────────────────────────────┘
                                 |
        +------------+-----------+------------+-----------+
        |            |           |            |           |
┌───────▼──┐  ┌─────▼───┐  ┌────▼────┐  ┌───▼────┐  ┌──▼─────┐
│ 实例 2048│  │实例 2049│  │实例 2050│  │实例 ...│  │实例 ...│
│ account_a│  │account_b│  │account_c│  │account_d│  │account_e│
└──────────┘  └─────────┘  └─────────┘  └────────┘  └────────┘
```

## 快速开始

### 1. 安装依赖

```bash
pip install aiohttp fastapi uvicorn psutil requests
```

### 2. 创建认证文件

为每个账号创建认证文件：

```bash
# 账号 A
python launch_camoufox.py --debug --save-auth-as account_a
# 登录后按提示保存

# 账号 B
python launch_camoufox.py --debug --save-auth-as account_b
# 登录后按提示保存

# 账号 C
python launch_camoufox.py --debug --save-auth-as account_c
# 登录后按提示保存
```

认证文件将保存在 `auth_profiles/saved/` 目录。

### 3. 配置多账号

创建配置文件：

```bash
python start_multi_account.py init
```

编辑 `multi_account_config.json`：

```json
{
  "accounts": [
    {
      "id": "account_a",
      "auth_file": "auth_profiles/saved/account_a.json",
      "port": 2048,
      "weight": 2,
      "enabled": true,
      "max_concurrent": 3
    },
    {
      "id": "account_b",
      "auth_file": "auth_profiles/saved/account_b.json",
      "port": 2049,
      "weight": 1,
      "enabled": true,
      "max_concurrent": 3
    },
    {
      "id": "account_c",
      "auth_file": "auth_profiles/saved/account_c.json",
      "port": 2050,
      "weight": 1,
      "enabled": true,
      "max_concurrent": 3
    }
  ],
  "router": {
    "port": 8080,
    "host": "0.0.0.0",
    "strategy": "roundrobin",
    "health_check_interval": 30,
    "health_check_timeout": 5,
    "auto_restart": true
  },
  "logging": {
    "level": "INFO",
    "file": "logs/router_manager.log"
  }
}
```

### 4. 启动系统

```bash
python start_multi_account.py start
```

系统将：
1. 启动进程管理器，为每个账号启动一个 camoufox 实例
2. 启动路由器，监听 8080 端口
3. 开始健康检查和自动监控

### 5. 测试 API

```bash
# 测试健康检查
curl http://127.0.0.1:8080/health

# 获取模型列表
curl http://127.0.0.1:8080/v1/models

# 测试聊天完成
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-1.5-pro",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 测试流式响应
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-1.5-pro",
    "messages": [{"role": "user", "content": "讲个故事"}],
    "stream": true
  }' --no-buffer
```

### 6. 查看状态

```bash
# 查看系统状态
python start_multi_account.py status

# 详细状态（通过 API）
curl http://127.0.0.1:8080/router/status
```

## 路由策略

### 1. 轮询（RoundRobin）

默认策略，请求按顺序分发到各个实例：

```json
{
  "router": {
    "strategy": "roundrobin"
  }
}
```

**特点**：
- 请求均匀分布
- 简单可靠
- 适合实例性能相近的场景

### 2. 权重（Weighted）

按权重分发请求，权重高的实例接收更多请求：

```json
{
  "accounts": [
    {
      "id": "powerful_account",
      "weight": 3,
      ...
    },
    {
      "id": "normal_account",
      "weight": 1,
      ...
    }
  ],
  "router": {
    "strategy": "weighted"
  }
}
```

**特点**：
- 灵活分配负载
- 适合实例性能不同的场景
- 高级账号可设置更高权重

### 3. 哈希（Hash）

基于 API Key 哈希，相同 API Key 的请求总是路由到同一实例：

```json
{
  "router": {
    "strategy": "hash"
  }
}
```

**特点**：
- 会话保持
- 适合需要一致性的场景
- 自动实现 API Key 到账号的映射

## 高级配置

### 健康检查

```json
{
  "router": {
    "health_check_interval": 30,  // 每30秒检查一次
    "health_check_timeout": 5,    // 超时5秒
    "auto_restart": true          // 自动重启失败实例
  }
}
```

### 并发控制

限制每个实例的最大并发请求数：

```json
{
  "accounts": [
    {
      "id": "account_a",
      "max_concurrent": 5,  // 最多5个并发请求
      ...
    }
  ]
}
```

### 日志配置

```json
{
  "logging": {
    "level": "DEBUG",  // DEBUG, INFO, WARNING, ERROR
    "file": "logs/router_manager.log"
  }
}
```

## 故障排除

### 实例启动失败

```bash
# 查看日志
tail -f logs/launch_app.log

# 检查端口占用
lsof -i :2048  # 检查实例端口
lsof -i :8080  # 检查路由器端口

# 手动测试实例
python launch_camoufox.py --headless \
  --active-auth-json auth_profiles/saved/account_a.json \
  --server-port 2048
```

### 健康检查失败

```bash
# 手动检查实例健康
curl http://127.0.0.1:2048/health

# 查看实例日志
grep "account_a" logs/router_manager.log
```

### 请求路由失败

```bash
# 查看路由器状态
curl http://127.0.0.1:8080/router/status

# 检查网络连接
netstat -tlnp | grep 8080  # 路由器
netstat -tlnp | grep 2048  # 实例1
netstat -tlnp | grep 2049  # 实例2
```

## 性能优化

### 1. 调整实例数量

根据负载调整账号数量：

- 低负载：2-3个账号
- 中负载：3-5个账号
- 高负载：5-10个账号

### 2. 优化权重分配

根据账号等级设置权重：

- 免费账号：weight=1
- 付费账号：weight=2-3
- 高级账号：weight=5

### 3. 调整健康检查频率

平衡检测灵敏度和性能：

```json
{
  "router": {
    "health_check_interval": 60  // 生产环境可调整为60秒
  }
}
```

## 监控指标

### 通过 API 获取监控数据

```bash
# 路由器状态
curl http://127.0.0.1:8080/router/status

# 响应示例
{
  "strategy": "roundrobin",
  "instances": [
    {
      "id": "account_a",
      "port": 2048,
      "weight": 2,
      "enabled": true,
      "status": "healthy",
      "current_concurrent": 1,
      "max_concurrent": 3,
      "total_requests": 152,
      "failed_requests": 2,
      "last_heartbeat": 1703123456.789
    }
  ]
}
```

### 关键指标

- `status`: 实例健康状态
- `current_concurrent`: 当前并发数
- `total_requests`: 总请求数
- `failed_requests`: 失败请求数
- `last_heartbeat`: 最后心跳时间

## 安全建议

### 1. 使用 API Key 认证

在 `auth_profiles/key.txt` 中添加 API Key：

```
sk-router-key-001
sk-router-key-002
```

### 2. 限制访问来源

```json
{
  "router": {
    "host": "127.0.0.1"  // 仅本地访问
  }
}
```

### 3. 使用反向代理

生产环境建议使用 Nginx 反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
    }
}
```

## 常见问题

### Q: 如何添加新账号？

A:
1. 使用 `launch_camoufox.py --debug --save-auth-as new_account` 创建认证
2. 复制认证文件到 `auth_profiles/saved/`
3. 编辑 `multi_account_config.json`，添加新账号配置
4. 重启系统：`python start_multi_account.py start`

### Q: 如何临时禁用某个账号？

A:
```json
{
  "accounts": [
    {
      "id": "account_a",
      "enabled": false,  // 设置为 false
      ...
    }
  ]
}
```

### Q: 如何查看详细日志？

A:
```bash
# 路由器日志
tail -f logs/router_manager.log

# 实例日志（在管理器日志中）
grep "account_a" logs/router_manager.log
```

### Q: 支持多少个账号？

A: 取决于系统资源：
- CPU: 每个实例需要 1-2 核
- 内存: 每个实例需要 200-300MB
- 端口: 每个实例需要 1 个端口

建议单台服务器运行 5-10 个实例。

### Q: 如何实现账号故障转移？

A: 系统已内置自动故障转移：
1. 健康检查检测到实例失败
2. 自动标记为 `unhealthy`
3. 路由策略自动跳过该实例
4. 如果 `auto_restart: true`，自动尝试重启

### Q: 如何监控请求分布？

A: 使用 `/router/status` API：
```bash
watch -n 5 'curl -s http://127.0.0.1:8080/router/status | jq ".instances[] | {id, total_requests}"'
```

## 故障处理流程

### 实例持续失败

1. 检查认证文件是否过期
2. 手动测试实例是否能启动
3. 查看日志分析具体错误
4. 如果账号被封，禁用该实例

### 路由器无响应

1. 检查端口是否被占用：`lsof -i :8080`
2. 检查进程是否存活：`ps aux | grep multi_account_router`
3. 重启路由器

### 所有实例不健康

1. 检查网络连接
2. 检查 Google AI Studio 服务状态
3. 检查认证文件是否全部过期
4. 重新生成认证文件

## 最佳实践

1. **定期更新认证文件**：每月更新一次
2. **监控失败率**：失败率超过 5% 时检查账号状态
3. **分散风险**：使用不同注册方式的账号
4. **权重调优**：根据账号等级调整权重
5. **日志审计**：定期查看日志，发现异常
6. **备份配置**：备份 `multi_account_config.json`

## 技术支持

如有问题，请查看：
- 日志文件：`logs/router_manager.log`
- 实例日志：在路由器日志中搜索实例 ID
- 配置文件：`multi_account_config.json`
- 认证文件：`auth_profiles/saved/`
