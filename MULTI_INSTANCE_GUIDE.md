# 多实例模式使用指南

## 概述

多实例模式允许您同时运行多个Camoufox实例，每个实例使用不同的认证文件，从而实现并发处理和负载均衡。

## 功能特性

1. **自动实例发现**: 自动扫描 `auth_profiles/active` 目录中的认证文件
2. **负载均衡**: 根据实例可用性和负载情况自动分配请求
3. **健康监控**: 自动监控实例健康状态，发现问题时尝试恢复
4. **并发处理**: 支持多个请求同时处理，提高系统吞吐量
5. **实例状态查看**: 提供API端点查看所有实例的状态

## 启用多实例模式

### 1. 准备认证文件

确保 `auth_profiles/active` 目录中有多个有效的认证文件：

```bash
auth_profiles/
└── active/
    ├── account1@gmail.com.json
    ├── account2@gmail.com.json
    └── account3@gmail.com.json
```

### 2. 启动多实例模式

使用 `--multi` 参数启动：

```bash
# 多实例 + 无头模式（推荐）
python launch_camoufox.py --multi --headless

# 多实例 + 调试模式
python launch_camoufox.py --multi --debug

# 多实例 + 虚拟显示模式（仅Linux）
python launch_camoufox.py --multi --virtual-display
```

### 3. 验证启动

启动后，您应该看到类似以下的日志：

```
🚀 启用多实例模式
发现 3 个认证文件，启动多实例模式
启动实例 instance_1 (端口: 9222, 认证文件: account1@gmail.com.json)
启动实例 instance_2 (端口: 9223, 认证文件: account2@gmail.com.json)
启动实例 instance_3 (端口: 9224, 认证文件: account3@gmail.com.json)
多实例模式启动成功: 3 个实例就绪
```

## API端点

### 健康检查

```bash
GET /health
```

返回示例：
```json
{
  "status": "healthy",
  "multi_instance_mode": true,
  "total_instances": 3,
  "ready_instances": 3,
  "busy_instances": 0,
  "error_instances": 0
}
```

### 实例状态查看

```bash
GET /v1/instances
```

返回示例：
```json
{
  "total_instances": 3,
  "ready_instances": 3,
  "busy_instances": 0,
  "error_instances": 0,
  "instances": [
    {
      "id": "instance_1",
      "status": "ready",
      "port": 9222,
      "auth_file": "account1@gmail.com.json",
      "ws_endpoint": "ws://127.0.0.1:9222/devtools/browser/...",
      "last_used": 1640995200.0,
      "error_count": 0,
      "current_request_id": null
    }
  ]
}
```

### 聊天完成（支持多实例）

```bash
POST /v1/chat/completions
```

请求会自动分配到可用的实例上处理。

## 工作原理

### 1. 实例管理

- **启动**: 为每个认证文件启动独立的Camoufox进程
- **端口分配**: 自动分配可用端口（从9222开始）
- **WebSocket连接**: 通过CDP协议连接到每个实例

### 2. 负载均衡

- **轮询策略**: 选择最少使用的可用实例
- **状态跟踪**: 实时跟踪实例状态（ready、busy、error）
- **故障转移**: 当实例不可用时，自动选择其他实例

### 3. 健康监控

- **定期检查**: 每30秒检查一次实例健康状态
- **进程监控**: 监控实例进程是否正常运行
- **自动恢复**: 检测到问题时尝试重启实例

## 测试

使用提供的测试脚本验证多实例功能：

```bash
python test_multi_instance.py
```

测试包括：
- 健康检查
- 实例状态查看
- 并发请求测试
- 性能统计

## 配置选项

### 环境变量

- `MULTI_INSTANCE_MODE`: 是否启用多实例模式（true/false）
- `CAMOUFOX_WS_ENDPOINT`: 单实例模式的WebSocket端点（多实例模式下无效）

### 启动参数

- `--multi`: 启用多实例模式
- `--headless`: 无头模式（推荐用于多实例）
- `--debug`: 调试模式
- `--virtual-display`: 虚拟显示模式（仅Linux）

## 故障排除

### 常见问题

1. **实例启动失败**
   - 检查认证文件是否有效
   - 确保端口未被占用
   - 查看日志了解具体错误

2. **请求失败**
   - 检查是否有可用实例
   - 查看实例状态是否正常
   - 检查网络连接

3. **性能问题**
   - 监控系统资源使用情况
   - 考虑调整实例数量
   - 检查认证文件的有效性

### 日志查看

多实例模式的日志会包含实例标识，例如：
```
[实例 instance_1] 收到请求
[实例 instance_2] 处理完成
```

### 监控实例状态

定期检查实例状态：
```bash
curl http://localhost:2048/v1/instances
```

## 注意事项

1. **资源消耗**: 每个实例都会消耗系统资源，请根据硬件配置调整实例数量
2. **认证文件**: 确保认证文件有效且未过期
3. **端口占用**: 每个实例需要独立的端口，确保有足够的可用端口
4. **网络连接**: 实例之间共享网络资源，注意带宽限制

## 性能优化建议

1. **实例数量**: 建议实例数量不超过CPU核心数
2. **内存分配**: 每个实例大约需要500MB-1GB内存
3. **存储空间**: 确保有足够的临时文件存储空间
4. **网络优化**: 使用稳定的网络连接，避免频繁断线

## 与单实例模式的区别

| 特性 | 单实例模式 | 多实例模式 |
|------|-----------|-----------|
| 并发处理 | 串行处理 | 并行处理 |
| 认证文件 | 单个文件 | 多个文件 |
| 资源消耗 | 较低 | 较高 |
| 故障恢复 | 单点故障 | 故障转移 |
| 性能 | 中等 | 高 |
| 复杂度 | 简单 | 中等 |