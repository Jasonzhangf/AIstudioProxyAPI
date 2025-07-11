# 多实例模式快速开始指南

## 🚀 快速启动

### 1. 调试模式（可见浏览器窗口）
```bash
python launch_camoufox.py --multi --debug
```

### 2. 无头模式（后台运行）
```bash
python launch_camoufox.py --multi --headless
```

### 3. 默认模式（自动检测）
```bash
python launch_camoufox.py --multi
```

## 📋 启动过程

启动后你会看到：

```
============================================================
🚀 启动多实例模式
   模式: 调试模式 (可见浏览器)
   认证文件数量: 3
============================================================

📋 发现的认证文件和端口分配:
   1. account1@gmail.com.json -> 端口 9267
   2. account2@gmail.com.json -> 端口 9245
   3. account3@gmail.com.json -> 端口 9301

🔧 启动前清理所有相关端口...
   清理端口 9267 (占用进程: [1234])
✅ 端口预清理完成

🔧 启动实例 instance_1 (固定端口: 9267, 文件: account1@gmail.com.json)...
🔄 监控实例 instance_1 启动 (认证文件: account1@gmail.com.json)...
   实例 instance_1: --- [内部Camoufox启动] 正在调用 camoufox.server.launch_server ...
✅ 实例 instance_1 启动成功！WebSocket: ws://127.0.0.1:9222/devtools/browser/...

📊 启动结果: 3/3 个实例成功启动
⏳ 等待实例完全就绪...
✅ 3 个实例就绪，0 个实例仍在启动中
🔍 健康检查线程已启动

🎉 多实例模式启动成功!
   总实例数: 3
   就绪实例: 3
   忙碌实例: 0
   错误实例: 0

📊 实例状态总览:
   总数: 3 | 就绪: 3 | 忙碌: 0 | 错误: 0 | 启动中: 0

实例ID       状态     端口  认证文件                  当前请求    
----------------------------------------------------------------------
instance_1   🟢 ready  9222  account1@gmail.com.json   -           
instance_2   🟢 ready  9223  account2@gmail.com.json   -           
instance_3   🟢 ready  9224  account3@gmail.com.json   -           

🌐 启动API服务器...
   监听地址: http://0.0.0.0:2048
   本地访问: http://localhost:2048
   健康检查: http://localhost:2048/health
   实例状态: http://localhost:2048/v1/instances
============================================================
```

## 🔍 监控实例状态

### 方法1：使用监控脚本（推荐）
```bash
python monitor_instances.py
```

### 方法2：HTTP API查询
```bash
# 健康检查
curl http://localhost:2048/health

# 实例状态
curl http://localhost:2048/v1/instances
```

## 🧪 测试功能

```bash
python test_multi_instance.py
```

## 🔧 故障排除

### 问题1：实例启动失败
**症状**: 看到 "❌ 实例 instance_X 启动失败"

**解决方案**:
1. 检查认证文件是否有效
2. 确保端口未被占用
3. 查看详细错误信息

### 问题2：没有可见浏览器窗口
**症状**: 使用 `--debug` 但没有看到浏览器窗口

**解决方案**:
1. 确保使用了 `--debug` 参数
2. 检查是否被强制设置为headless模式
3. 查看启动日志确认模式

### 问题3：请求处理失败
**症状**: API请求返回错误

**解决方案**:
1. 检查实例状态：`curl http://localhost:2048/v1/instances`
2. 查看是否有就绪的实例
3. 检查认证文件是否过期

## 📊 状态指示器

- 🟢 **ready**: 实例就绪，可以处理请求
- 🟡 **busy**: 实例正在处理请求
- 🔴 **error**: 实例出现错误
- 🔵 **starting**: 实例正在启动
- ⚫ **stopped**: 实例已停止

## 🔧 端口管理

### 固定端口分配
- 每个认证文件会分配到固定的端口（基于文件名哈希）
- 相同的认证文件每次都会使用相同的端口
- 避免了端口冲突和重复分配问题

### 端口清理工具
```bash
# 查看端口分配情况
python cleanup_ports.py --list

# 清理所有分配的端口
python cleanup_ports.py --all

# 清理指定端口
python cleanup_ports.py --port 9222 9223
```

### 端口冲突处理
- 启动前会自动清理所有相关端口
- 发现端口被占用时会自动终止占用进程
- 如果无法清理端口，会显示详细错误信息

## 💡 最佳实践

1. **调试模式**: 适合开发和调试，可以看到浏览器窗口
2. **无头模式**: 适合生产环境，节省资源
3. **监控状态**: 定期检查实例状态，确保服务正常
4. **认证文件**: 确保使用有效的认证文件，定期更新
5. **端口管理**: 重启前使用端口清理工具确保环境清洁

## 🔄 实时状态

启动后，你会看到请求处理的实时信息：

```
📨 请求 abc123 -> 实例 instance_1
✅ 请求 abc123 处理完成

📨 请求 def456 -> 实例 instance_2  
✅ 请求 def456 处理完成
```

## 🛑 停止服务

按 `Ctrl+C` 停止服务，系统会自动清理所有实例。