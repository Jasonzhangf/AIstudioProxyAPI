#!/usr/bin/env python3
"""
多账号进程管理器
负责启动、监控和管理多个 camoufox 实例
"""

import os
import sys
import json
import time
import signal
import asyncio
import subprocess
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import logging.handlers
import psutil


@dataclass
class AccountInstance:
    """账号实例状态"""
    id: str
    auth_file: str
    port: int
    weight: int
    enabled: bool
    max_concurrent: int
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    status: str = "stopped"  # stopped, starting, running, failed
    last_heartbeat: Optional[float] = None
    restart_count: int = 0
    error_message: Optional[str] = None


class ProcessManager:
    """进程管理器"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self.instances: Dict[str, AccountInstance] = {}
        self.logger = self._setup_logging()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志系统"""
        logger = logging.getLogger("ProcessManager")
        logger.setLevel(getattr(logging, self.config.get("logging", {}).get("level", "INFO")))
        
        # 文件日志
        log_file = self.config.get("logging", {}).get("file", "logs/router_manager.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s'
        ))
        
        # 控制台日志
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        self.logger.info(f"接收到信号 {signal.Signals(signum).name}，正在优雅退出...")
        self.stop()
    
    def initialize_instances(self):
        """初始化所有账号实例"""
        self.logger.info("=" * 60)
        self.logger.info("初始化账号实例...")
        
        accounts = self.config.get("accounts", [])
        if not accounts:
            self.logger.warning("配置文件中未找到账号配置")
            return
        
        for account_config in accounts:
            instance = AccountInstance(
                id=account_config["id"],
                auth_file=account_config["auth_file"],
                port=account_config["port"],
                weight=account_config.get("weight", 1),
                enabled=account_config.get("enabled", True),
                max_concurrent=account_config.get("max_concurrent", 3)
            )
            self.instances[instance.id] = instance
            self.logger.info(f"  ✓ 初始化账号实例: {instance.id} (端口: {instance.port})")
        
        self.logger.info(f"共初始化 {len(self.instances)} 个账号实例")
        self.logger.info("=" * 60)
    
    def start_instance(self, instance_id: str) -> bool:
        """启动单个实例"""
        if instance_id not in self.instances:
            self.logger.error(f"账号实例不存在: {instance_id}")
            return False
        
        instance = self.instances[instance_id]
        
        if instance.status == "running":
            self.logger.warning(f"账号实例已在运行: {instance_id}")
            return True
        
        if not instance.enabled:
            self.logger.warning(f"账号实例已禁用: {instance_id}")
            return False
        
        # 检查端口是否被占用
        if self._is_port_in_use(instance.port):
            self.logger.error(f"端口 {instance.port} 已被占用，无法启动 {instance_id}")
            instance.status = "failed"
            instance.error_message = f"端口 {instance.port} 被占用"
            return False
        
        # 检查认证文件是否存在
        auth_file_path = os.path.abspath(instance.auth_file)
        if not os.path.exists(auth_file_path):
            self.logger.error(f"认证文件不存在: {auth_file_path}")
            instance.status = "failed"
            instance.error_message = f"认证文件不存在: {auth_file_path}"
            return False
        
        # 构建启动命令
        cmd = [
            sys.executable, "-u", "launch_camoufox.py",
            "--headless",
            "--active-auth-json", auth_file_path,
            "--server-port", str(instance.port),
            "--stream-port", "0"  # 禁用流式代理，由路由器统一处理
        ]
        
        self.logger.info(f"启动账号实例: {instance_id} (端口: {instance.port})")
        self.logger.debug(f"执行命令: {' '.join(cmd)}")
        
        try:
            # 启动进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )
            
            instance.process = process
            instance.pid = process.pid
            instance.status = "starting"
            instance.last_heartbeat = time.time()
            
            # 启动日志监控线程
            threading.Thread(
                target=self._monitor_instance_logs,
                args=(instance_id,),
                daemon=True
            ).start()
            
            self.logger.info(f"  ✓ 进程已启动 (PID: {process.pid})")
            return True
            
        except Exception as e:
            self.logger.error(f"启动账号实例失败 {instance_id}: {e}", exc_info=True)
            instance.status = "failed"
            instance.error_message = str(e)
            return False
    
    def stop_instance(self, instance_id: str) -> bool:
        """停止单个实例"""
        if instance_id not in self.instances:
            self.logger.error(f"账号实例不存在: {instance_id}")
            return False
        
        instance = self.instances[instance_id]
        
        if not instance.process:
            self.logger.warning(f"账号实例未运行: {instance_id}")
            return True
        
        self.logger.info(f"停止账号实例: {instance_id} (PID: {instance.pid})")
        
        try:
            # 终止进程
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(instance.pid)], 
                             capture_output=True, timeout=5)
            else:
                # 尝试优雅终止
                instance.process.terminate()
                try:
                    instance.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 强制杀死
                    self.logger.warning(f"优雅终止超时，强制杀死进程 {instance.pid}")
                    instance.process.kill()
                    instance.process.wait()
            
            instance.process = None
            instance.pid = None
            instance.status = "stopped"
            instance.last_heartbeat = None
            
            self.logger.info(f"  ✓ 账号实例已停止: {instance_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"停止账号实例失败 {instance_id}: {e}", exc_info=True)
            return False
    
    def start_all(self):
        """启动所有启用的实例"""
        self.logger.info("=" * 60)
        self.logger.info("启动所有账号实例...")
        
        started = 0
        failed = 0
        
        for instance_id, instance in self.instances.items():
            if instance.enabled:
                if self.start_instance(instance_id):
                    started += 1
                else:
                    failed += 1
                # 间隔启动，避免资源竞争
                time.sleep(2)
        
        self.logger.info(f"启动完成: 成功={started}, 失败={failed}")
        self.logger.info("=" * 60)
        
        return started, failed
    
    def stop_all(self):
        """停止所有实例"""
        self.logger.info("=" * 60)
        self.logger.info("停止所有账号实例...")
        
        stopped = 0
        failed = 0
        
        for instance_id in list(self.instances.keys()):
            if self.stop_instance(instance_id):
                stopped += 1
            else:
                failed += 1
        
        self.logger.info(f"停止完成: 成功={stopped}, 失败={failed}")
        self.logger.info("=" * 60)
        
        return stopped, failed
    
    def get_instance_status(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """获取实例状态"""
        if instance_id not in self.instances:
            return None
        
        instance = self.instances[instance_id]
        return {
            "id": instance.id,
            "status": instance.status,
            "pid": instance.pid,
            "port": instance.port,
            "weight": instance.weight,
            "enabled": instance.enabled,
            "restart_count": instance.restart_count,
            "error_message": instance.error_message,
            "last_heartbeat": instance.last_heartbeat
        }
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        """获取所有实例状态"""
        return [self.get_instance_status(iid) for iid in self.instances.keys()]
    
    def start_monitor(self):
        """启动监控线程"""
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("监控线程已启动")
    
    def _monitor_loop(self):
        """监控循环"""
        interval = self.config.get("router", {}).get("health_check_interval", 30)
        
        while not self._stop_event.is_set():
            try:
                self._check_health()
            except Exception as e:
                self.logger.error(f"健康检查出错: {e}", exc_info=True)
            
            # 等待下一次检查
            self._stop_event.wait(interval)
    
    def _check_health(self):
        """检查所有实例健康状态"""
        for instance_id, instance in self.instances.items():
            if not instance.enabled or instance.status == "stopped":
                continue
            
            # 检查进程是否存活
            if instance.process:
                ret_code = instance.process.poll()
                if ret_code is not None:
                    # 进程已退出
                    self.logger.warning(f"实例 {instance_id} 已退出 (退出码: {ret_code})")
                    instance.status = "failed"
                    instance.error_message = f"进程退出 (码: {ret_code})"
                    
                    # 自动重启
                    if self.config.get("router", {}).get("auto_restart", True):
                        self.logger.info(f"尝试重启实例 {instance_id}...")
                        instance.restart_count += 1
                        self.stop_instance(instance_id)
                        time.sleep(2)
                        self.start_instance(instance_id)
            
            # 检查端口是否响应
            if instance.status == "running":
                if self._is_port_in_use(instance.port):
                    instance.last_heartbeat = time.time()
                else:
                    self.logger.warning(f"实例 {instance_id} 端口 {instance.port} 无响应")
                    instance.status = "failed"
    
    def _monitor_instance_logs(self, instance_id: str):
        """监控实例日志"""
        instance = self.instances[instance_id]
        
        if not instance.process:
            return
        
        # 监控 stdout
        def log_stream(stream, level):
            try:
                for line in iter(stream.readline, b''):
                    if line:
                        self.logger.log(level, f"[{instance_id}] {line.decode('utf-8', errors='replace').strip()}")
            except Exception as e:
                self.logger.debug(f"日志监控结束 {instance_id}: {e}")
        
        # 启动日志监控线程
        if instance.process.stdout:
            threading.Thread(target=log_stream, args=(instance.process.stdout, logging.INFO), daemon=True).start()
        
        if instance.process.stderr:
            threading.Thread(target=log_stream, args=(instance.process.stderr, logging.ERROR), daemon=True).start()
    
    def _is_port_in_use(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(('127.0.0.1', port)) == 0
        except Exception:
            return False
    
    def stop(self):
        """停止管理器"""
        self.logger.info("正在停止进程管理器...")
        self._stop_event.set()
        
        # 停止所有实例
        self.stop_all()
        
        # 等待监控线程结束
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        
        self.logger.info("进程管理器已停止")


def main():
    """主函数"""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "multi_account_config.json"
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)
    
    manager = ProcessManager(config_path)
    manager.initialize_instances()
    
    try:
        # 启动所有实例
        manager.start_all()
        
        # 启动监控
        manager.start_monitor()
        
        # 保持主线程运行
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n接收到 Ctrl+C，正在退出...")
    finally:
        manager.stop()


if __name__ == "__main__":
    main()