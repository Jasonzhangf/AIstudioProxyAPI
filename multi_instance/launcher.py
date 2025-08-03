"""
多实例启动器
负责启动多个 Camoufox 实例并管理它们的生命周期
"""
import asyncio
import os
import subprocess
import signal
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import threading
import queue
import re

class MultiInstanceLauncher:
    """多实例启动器"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.camoufox_processes: Dict[str, subprocess.Popen] = {}
        self.instance_configs: List[Dict[str, any]] = []
        self.base_port = 9222
        self.ws_endpoints: Dict[str, str] = {}
        self.launch_mode = "headless"
        self.proxy_config = None
        self.simulated_os = "linux"
        
        # WebSocket 端点正则表达式
        self.ws_regex = re.compile(r"(ws://\S+)")
        
        # 注册清理函数
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info(f"收到信号 {signum}，开始清理多实例...")
        self.cleanup_all_instances()
    
    def discover_auth_profiles(self, auth_profiles_dir: str = "auth_profiles") -> List[Dict[str, str]]:
        """发现认证配置文件 - 多实例模式专用，只读取multi文件夹"""
        profiles = []
        auth_path = Path(auth_profiles_dir)
        
        # 只搜索 multi 目录
        profile_dir = auth_path / 'multi'
        if not profile_dir.exists():
            self.logger.warning(f"多实例配置目录不存在: {profile_dir}")
            return profiles
            
        # 获取所有json文件并排序以确保一致的顺序
        auth_files = sorted(profile_dir.glob("*.json"))
        
        for auth_file in auth_files:
            try:
                # 跳过时间戳文件
                if auth_file.stem.startswith("auth_state_"):
                    continue
                    
                # 验证是否为有效的认证文件
                with open(auth_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'cookies' in data:  # 基本验证
                        profiles.append({
                            'email': auth_file.stem,
                            'auth_file': str(auth_file),
                            'directory': 'multi'
                        })
                        
            except Exception as e:
                self.logger.warning(f"跳过无效认证文件 {auth_file}: {e}")
        
        # 按email排序确保一致性
        profiles.sort(key=lambda x: x['email'])
        return profiles
    
    def create_instance_configs(self, profiles: List[Dict[str, str]], 
                              launch_mode: str = "headless",
                              proxy_config: str = None,
                              simulated_os: str = "linux") -> List[Dict[str, any]]:
        """创建实例配置"""
        configs = []
        base_stream_port = 3120  # 基础STREAM端口
        
        for i, profile in enumerate(profiles):
            instance_id = f"instance_{i+1}_{profile['email'].replace('@', '_at_').replace('.', '_')}"
            port = self.base_port + i
            stream_port = base_stream_port + i  # 为每个实例分配独立的STREAM端口
            
            config = {
                'instance_id': instance_id,
                'email': profile['email'],
                'auth_file': profile['auth_file'],
                'port': port,
                'stream_port': stream_port,  # 新增STREAM端口
                'launch_mode': launch_mode,
                'proxy_config': proxy_config,
                'simulated_os': simulated_os,
                'index': i
            }
            
            configs.append(config)
            self.logger.info(f"创建实例配置: {instance_id} (Camoufox端口: {port}, STREAM端口: {stream_port}, 认证: {profile['email']})")
        
        return configs
    
    def _enqueue_output(self, stream, stream_name: str, output_queue: queue.Queue, process_pid: str):
        """线程安全的输出队列处理"""
        log_prefix = f"[读取线程-{stream_name}-PID:{process_pid}]"
        try:
            for line_bytes in iter(stream.readline, b''):
                if not line_bytes:
                    break
                try:
                    line_str = line_bytes.decode('utf-8', errors='replace')
                    output_queue.put((stream_name, line_str))
                except Exception as decode_err:
                    self.logger.warning(f"{log_prefix} 解码错误: {decode_err}")
                    output_queue.put((stream_name, f"[解码错误: {decode_err}]\n"))
        except Exception as e:
            self.logger.error(f"{log_prefix} 读取流时发生错误: {e}")
        finally:
            output_queue.put((stream_name, None))
    
    def _capture_ws_endpoint(self, config: Dict[str, any], timeout: int = 45) -> Optional[str]:
        """启动单个 Camoufox 实例并捕获 WebSocket 端点"""
        instance_id = config['instance_id']
        
        try:
            # 构建启动命令 - 使用内部启动模式避免循环
            cmd = [
                'python', 'launch_camoufox.py',
                '--internal-launch',
                f'--internal-launch-mode={config["launch_mode"]}',
                f'--internal-auth-file={config["auth_file"]}',
                f'--internal-camoufox-port={config["port"]}',
                f'--internal-camoufox-os={config["simulated_os"]}',
                f'--stream-port={config["stream_port"]}',  # 传递STREAM端口
                '--no-server'  # 不启动 FastAPI 服务器，只启动 Camoufox
            ]
            
            if config['proxy_config']:
                cmd.append(f'--internal-camoufox-proxy={config["proxy_config"]}')
            
            self.logger.info(f"启动实例 {instance_id}，命令: {' '.join(cmd)}")
            
            # 启动进程
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False  # 使用二进制模式以便正确处理编码
            )
            
            self.camoufox_processes[instance_id] = proc
            
            # 创建输出队列
            output_queue = queue.Queue()
            
            # 启动读取线程
            stdout_thread = threading.Thread(
                target=self._enqueue_output,
                args=(proc.stdout, 'stdout', output_queue, str(proc.pid))
            )
            stderr_thread = threading.Thread(
                target=self._enqueue_output,
                args=(proc.stderr, 'stderr', output_queue, str(proc.pid))
            )
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # 监控输出并捕获 WebSocket 端点
            start_time = time.time()
            ws_endpoint = None
            
            while time.time() - start_time < timeout:
                if proc.poll() is not None:
                    self.logger.error(f"实例 {instance_id} 进程意外退出，返回码: {proc.returncode}")
                    break
                
                try:
                    stream_name, line = output_queue.get(timeout=1)
                    if line is None:  # 线程结束标志
                        continue
                    
                    # 记录输出（可选）
                    self.logger.debug(f"[{instance_id}] {stream_name}: {line.strip()}")
                    
                    # 搜索 WebSocket 端点
                    ws_match = self.ws_regex.search(line)
                    if ws_match:
                        ws_endpoint = ws_match.group(1)
                        self.logger.info(f"实例 {instance_id} WebSocket 端点: {ws_endpoint}")
                        break
                        
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"处理实例 {instance_id} 输出时出错: {e}")
                    break
            
            if ws_endpoint:
                self.ws_endpoints[instance_id] = ws_endpoint
                self.logger.info(f"✅ 实例 {instance_id} 启动成功")
                return ws_endpoint
            else:
                self.logger.error(f"❌ 实例 {instance_id} 启动失败：未能捕获 WebSocket 端点")
                self.cleanup_instance(instance_id)
                return None
                
        except Exception as e:
            self.logger.error(f"启动实例 {instance_id} 时发生异常: {e}")
            self.cleanup_instance(instance_id)
            return None
    
    def _cleanup_ports(self, configs: List[Dict[str, any]]):
        """清理所有需要的端口"""
        camoufox_ports = [config['port'] for config in configs]
        stream_ports = [config['stream_port'] for config in configs]
        all_ports = camoufox_ports + stream_ports
        
        self.logger.info(f"检查并清理端口: Camoufox端口{camoufox_ports}, STREAM端口{stream_ports}")
        
        for port in all_ports:
            try:
                # 查找占用端口的进程
                import subprocess
                import platform
                
                system_platform = platform.system()
                pids = []
                
                if system_platform == "Linux" or system_platform == "Darwin":
                    try:
                        result = subprocess.run(
                            ['lsof', '-ti', f':{port}', '-sTCP:LISTEN'],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0 and result.stdout:
                            pids = [int(pid) for pid in result.stdout.strip().split('\n') if pid.isdigit()]
                    except subprocess.TimeoutExpired:
                        self.logger.warning(f"查找端口 {port} 进程超时")
                    except FileNotFoundError:
                        self.logger.warning(f"lsof 命令未找到，跳过端口 {port} 清理")
                
                elif system_platform == "Windows":
                    try:
                        result = subprocess.run(
                            ['netstat', '-ano', '-p', 'TCP'],
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode == 0:
                            for line in result.stdout.strip().split('\n'):
                                if f":{port}" in line and "LISTENING" in line:
                                    parts = line.split()
                                    if len(parts) >= 4 and parts[-1].isdigit():
                                        pids.append(int(parts[-1]))
                    except subprocess.TimeoutExpired:
                        self.logger.warning(f"查找端口 {port} 进程超时")
                
                # 强制杀死占用端口的进程
                if pids:
                    self.logger.info(f"端口 {port} 被进程 {pids} 占用，正在清理...")
                    for pid in pids:
                        try:
                            import os
                            import signal
                            os.kill(pid, signal.SIGTERM)
                            # 给进程一些时间优雅退出
                            import time
                            time.sleep(0.5)
                            # 如果还在运行，强制杀死
                            try:
                                os.kill(pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass  # 进程已经退出
                        except ProcessLookupError:
                            pass  # 进程已经不存在
                        except PermissionError:
                            self.logger.warning(f"没有权限杀死进程 {pid}")
                        except Exception as e:
                            self.logger.warning(f"清理进程 {pid} 时出错: {e}")
                    
                    self.logger.info(f"✅ 端口 {port} 已清理")
                else:
                    self.logger.debug(f"端口 {port} 未被占用")
                    
            except Exception as e:
                self.logger.error(f"清理端口 {port} 时出错: {e}")

    def launch_all_instances(self, configs: List[Dict[str, any]], 
                           max_concurrent: int = 3,
                           startup_delay: int = 2) -> Dict[str, str]:
        """启动所有实例"""
        self.instance_configs = configs
        successful_endpoints = {}
        
        self.logger.info(f"开始启动 {len(configs)} 个实例...")
        
        # 首先清理所有需要的端口
        self._cleanup_ports(configs)
        
        # 分批启动实例以避免资源争用
        for i in range(0, len(configs), max_concurrent):
            batch = configs[i:i + max_concurrent]
            self.logger.info(f"启动第 {i//max_concurrent + 1} 批实例 ({len(batch)} 个)...")
            
            # 并发启动当前批次
            batch_results = {}
            threads = []
            
            def start_instance_thread(config):
                ws_endpoint = self._capture_ws_endpoint(config)
                if ws_endpoint:
                    batch_results[config['instance_id']] = ws_endpoint
            
            for config in batch:
                thread = threading.Thread(target=start_instance_thread, args=(config,))
                thread.start()
                threads.append(thread)
                
                # 错开启动时间
                time.sleep(startup_delay)
            
            # 等待当前批次完成
            for thread in threads:
                thread.join()
            
            successful_endpoints.update(batch_results)
            
            self.logger.info(f"第 {i//max_concurrent + 1} 批完成，成功启动 {len(batch_results)} 个实例")
        
        self.logger.info(f"所有实例启动完成，成功: {len(successful_endpoints)}/{len(configs)}")
        return successful_endpoints
    
    def cleanup_instance(self, instance_id: str):
        """清理单个实例"""
        if instance_id in self.camoufox_processes:
            proc = self.camoufox_processes[instance_id]
            try:
                if proc.poll() is None:  # 进程仍在运行
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                
                del self.camoufox_processes[instance_id]
                self.logger.info(f"实例 {instance_id} 已清理")
            except Exception as e:
                self.logger.error(f"清理实例 {instance_id} 时出错: {e}")
        
        # 清理端点记录
        if instance_id in self.ws_endpoints:
            del self.ws_endpoints[instance_id]
    
    def cleanup_all_instances(self):
        """清理所有实例"""
        self.logger.info("开始清理所有实例...")
        
        for instance_id in list(self.camoufox_processes.keys()):
            self.cleanup_instance(instance_id)
        
        self.logger.info("所有实例已清理完成")
    
    def get_instance_endpoints(self) -> Dict[str, str]:
        """获取所有实例的 WebSocket 端点"""
        return self.ws_endpoints.copy()
    
    def is_instance_running(self, instance_id: str) -> bool:
        """检查实例是否仍在运行"""
        if instance_id not in self.camoufox_processes:
            return False
        
        proc = self.camoufox_processes[instance_id]
        return proc.poll() is None
    
    def get_running_instances(self) -> List[str]:
        """获取正在运行的实例列表"""
        running = []
        for instance_id in list(self.camoufox_processes.keys()):
            if self.is_instance_running(instance_id):
                running.append(instance_id)
            else:
                # 清理已停止的实例
                self.cleanup_instance(instance_id)
        return running
    
    def restart_instance(self, instance_id: str) -> bool:
        """重启指定实例"""
        # 找到原始配置
        config = None
        for cfg in self.instance_configs:
            if cfg['instance_id'] == instance_id:
                config = cfg
                break
        
        if not config:
            self.logger.error(f"未找到实例 {instance_id} 的配置")
            return False
        
        # 清理旧实例
        self.cleanup_instance(instance_id)
        
        # 启动新实例
        ws_endpoint = self._capture_ws_endpoint(config)
        return ws_endpoint is not None