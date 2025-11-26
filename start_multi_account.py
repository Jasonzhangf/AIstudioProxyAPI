#!/usr/bin/env python3
"""
多账号管理器启动脚本
一键启动进程管理器和路由器
"""

import os
import sys
import time
import signal
import subprocess
import argparse
from pathlib import Path


def check_dependencies():
    """检查必要的依赖"""
    print("检查依赖...")
    
    # 检查配置文件
    config_files = [
        "multi_account_config.json",
        "multi_account_manager.py",
        "multi_account_router.py"
    ]
    
    for file in config_files:
        if not os.path.exists(file):
            print(f"❌ 缺少必要文件: {file}")
            print("请确保所有文件都在当前目录")
            sys.exit(1)
    
    # 检查 Python 包
    try:
        import aiohttp
        import fastapi
        import uvicorn
    except ImportError as e:
        print(f"❌ 缺少 Python 包: {e}")
        print("请运行: pip install aiohttp fastapi uvicorn")
        sys.exit(1)
    
    print("✅ 依赖检查通过")


def check_auth_files():
    """检查认证文件"""
    print("检查认证文件...")
    
    if not os.path.exists("multi_account_config.json"):
        print("❌ 配置文件不存在")
        return False
    
    with open("multi_account_config.json", 'r') as f:
        config = json.load(f)
    
    accounts = config.get("accounts", [])
    if not accounts:
        print("⚠️  配置文件中未找到账号配置")
        return False
    
    missing_files = []
    for account in accounts:
        auth_file = account.get("auth_file", "")
        if not auth_file:
            missing_files.append(f"账号 {account.get('id', 'unknown')} 缺少 auth_file")
            continue
        
        if not os.path.exists(auth_file):
            missing_files.append(f"认证文件不存在: {auth_file}")
    
    if missing_files:
        print("❌ 发现以下问题:")
        for msg in missing_files:
            print(f"   - {msg}")
        print("\n请先创建认证文件:")
        print("  1. 使用 launch_camoufox.py --debug 登录并保存认证")
        print("  2. 将生成的文件复制到 auth_profiles/saved/ 目录")
        print("  3. 更新 multi_account_config.json 中的路径")
        return False
    
    print(f"✅ 认证文件检查通过 ({len(accounts)} 个账号)")
    return True


def run_manager(config_path: str):
    """运行进程管理器"""
    print("\n" + "=" * 60)
    print("启动进程管理器...")
    print("=" * 60)
    
    cmd = [sys.executable, "multi_account_manager.py", config_path]
    
    try:
        process = subprocess.Popen(cmd)
        print(f"进程管理器已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ 启动进程管理器失败: {e}")
        return None


def run_router(config_path: str):
    """运行路由器"""
    print("\n" + "=" * 60)
    print("启动路由器...")
    print("=" * 60)
    
    cmd = [sys.executable, "multi_account_router.py", config_path]
    
    try:
        process = subprocess.Popen(cmd)
        print(f"路由器已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ 启动路由器失败: {e}")
        return None


def show_status():
    """显示状态"""
    print("\n" + "=" * 60)
    print("系统状态")
    print("=" * 60)
    
    try:
        import requests
        
        # 检查路由器
        try:
            resp = requests.get("http://127.0.0.1:8080/router/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print(f"路由器状态: 运行中")
                print(f"路由策略: {data.get('strategy', 'unknown')}")
                print(f"后端实例:")
                
                for inst in data.get('instances', []):
                    status_icon = "✅" if inst['status'] == 'healthy' else "❌"
                    print(f"  {status_icon} {inst['id']} (端口: {inst['port']}, "
                          f"状态: {inst['status']}, 并发: {inst['current_concurrent']}/"
                          f"{inst['max_concurrent']})")
            else:
                print(f"路由器状态: 异常 (HTTP {resp.status_code})")
        except requests.exceptions.ConnectionError:
            print("路由器状态: 未启动或无法连接")
        except Exception as e:
            print(f"检查路由器状态失败: {e}")
        
        # 检查每个后端实例
        print("\n后端实例健康检查:")
        if os.path.exists("multi_account_config.json"):
            with open("multi_account_config.json", 'r') as f:
                config = json.load(f)
            
            accounts = config.get("accounts", [])
            for account in accounts:
                port = account.get("port")
                if port:
                    try:
                        resp = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
                        status = "✅ 健康" if resp.status_code == 200 else f"❌ 异常 (HTTP {resp.status_code})"
                    except:
                        status = "❌ 无法连接"
                    
                    print(f"  {account['id']} (端口: {port}): {status}")
    
    except ImportError:
        print("❌ 需要 requests 包，请安装: pip install requests")


def test_api():
    """测试 API"""
    print("\n" + "=" * 60)
    print("测试 API")
    print("=" * 60)
    
    try:
        import requests
        
        # 测试路由器
        print("\n1. 测试路由器健康检查...")
        try:
            resp = requests.get("http://127.0.0.1:8080/health")
            print(f"   状态: {'✅ 正常' if resp.status_code == 200 else '❌ 异常'}")
            if resp.status_code == 200:
                print(f"   响应: {resp.json()}")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
        
        # 测试模型列表
        print("\n2. 测试模型列表...")
        try:
            resp = requests.get("http://127.0.0.1:8080/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get('data', [])
                print(f"   ✅ 成功，获取到 {len(models)} 个模型")
                if models:
                    print(f"   前3个模型:")
                    for i, model in enumerate(models[:3]):
                        print(f"     - {model.get('id', 'unknown')}")
            else:
                print(f"   ❌ 失败 (HTTP {resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
        
        # 测试聊天完成
        print("\n3. 测试聊天完成（非流式）...")
        try:
            resp = requests.post(
                "http://127.0.0.1:8080/v1/chat/completions",
                json={
                    "model": "gemini-1.5-pro",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 10
                },
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"   ✅ 成功，响应: {content[:100]}...")
            else:
                print(f"   ❌ 失败 (HTTP {resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
    
    except ImportError:
        print("❌ 需要 requests 包，请安装: pip install requests")


def create_sample_config():
    """创建示例配置"""
    if os.path.exists("multi_account_config.json"):
        print("配置文件已存在，跳过创建")
        return
    
    print("\n" + "=" * 60)
    print("创建示例配置文件...")
    print("=" * 60)
    
    sample_config = {
        "accounts": [
            {
                "id": "account_1",
                "auth_file": "auth_profiles/saved/auth_state_1732601234.json",
                "port": 2048,
                "weight": 1,
                "enabled": True,
                "max_concurrent": 3
            }
        ],
        "router": {
            "port": 8080,
            "host": "0.0.0.0",
            "strategy": "roundrobin",
            "health_check_interval": 30,
            "health_check_timeout": 5,
            "auto_restart": True
        },
        "logging": {
            "level": "INFO",
            "file": "logs/router_manager.log"
        }
    }
    
    with open("multi_account_config.json", 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print("✅ 示例配置文件已创建: multi_account_config.json")
    print("\n请按以下步骤操作:")
    print("  1. 使用 launch_camoufox.py --debug 登录并保存认证")
    print("  2. 将生成的 auth_state_*.json 文件复制到 auth_profiles/saved/")
    print("  3. 编辑 multi_account_config.json，添加账号配置")
    print("  4. 运行: python start_multi_account.py start")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="多账号管理器启动脚本")
    parser.add_argument("command", choices=["start", "status", "test", "init", "stop"], 
                       default="start", nargs="?", help="命令")
    parser.add_argument("--config", default="multi_account_config.json", 
                       help="配置文件路径 (默认: multi_account_config.json)")
    
    args = parser.parse_args()
    
    # 检查依赖
    check_dependencies()
    
    if args.command == "init":
        create_sample_config()
        return
    
    # 检查配置文件
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        print(f"请运行 'python {sys.argv[0]} init' 创建示例配置")
        sys.exit(1)
    
    if args.command == "start":
        # 检查认证文件
        if not check_auth_files():
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("启动多账号管理系统")
        print("=" * 60)
        
        # 启动管理器
        manager_process = run_manager(args.config)
        if not manager_process:
            sys.exit(1)
        
        # 等待管理器启动
        print("\n等待管理器初始化...")
        time.sleep(3)
        
        # 启动路由器
        router_process = run_router(args.config)
        if not router_process:
            manager_process.terminate()
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("系统启动完成!")
        print("=" * 60)
        print(f"路由器地址: http://127.0.0.1:8080")
        print(f"管理接口: http://127.0.0.1:8080/router/status")
        print(f"API 端点: http://127.0.0.1:8080/v1/chat/completions")
        print("\n按 Ctrl+C 停止系统")
        
        try:
            # 等待进程
            while True:
                # 检查进程是否存活
                if manager_process.poll() is not None:
                    print("\n❌ 管理器进程异常退出")
                    router_process.terminate()
                    break
                
                if router_process.poll() is not None:
                    print("\n❌ 路由器进程异常退出")
                    manager_process.terminate()
                    break
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n\n接收到 Ctrl+C，正在停止系统...")
            manager_process.terminate()
            router_process.terminate()
            
            # 等待进程结束
            try:
                manager_process.wait(timeout=5)
                router_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                manager_process.kill()
                router_process.kill()
            
            print("系统已停止")
    
    elif args.command == "status":
        show_status()
    
    elif args.command == "test":
        test_api()
    
    elif args.command == "stop":
        print("停止功能未实现，请使用 Ctrl+C 停止")


if __name__ == "__main__":
    main()
