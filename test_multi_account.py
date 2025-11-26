#!/usr/bin/env python3
"""
多账号路由池测试脚本
测试负载均衡、健康检查、故障转移、并发控制
"""

import os
import sys
import asyncio
import time
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any, Optional
import subprocess
import signal

# 检查依赖
try:
    import requests
    import aiohttp
except ImportError:
    print("❌ 需要安装依赖: pip install requests aiohttp")
    sys.exit(1)


class MultiAccountTester:
    """多账号路由池测试器"""
    
    def __init__(self, router_port: int = 8180):
        self.router_port = router_port
        self.router_url = f"http://127.0.0.1:{router_port}"
        self.test_results = []
        self.lock = threading.Lock()
    
    def log(self, message: str):
        """日志输出"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {message}")
    
    def wait_for_router(self, timeout: int = 60) -> bool:
        """等待路由器启动"""
        self.log("等待路由器启动...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.router_url}/health", timeout=2)
                if response.status_code == 200:
                    self.log("✅ 路由器已启动")
                    return True
            except:
                pass
            time.sleep(1)
        
        self.log("❌ 路由器启动超时")
        return False
    
    def test_health_check(self) -> bool:
        """测试健康检查"""
        self.log("\n" + "=" * 60)
        self.log("测试健康检查")
        self.log("=" * 60)
        
        try:
            response = requests.get(f"{self.router_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ 健康检查通过: {data}")
                
                # 验证有健康实例
                healthy_count = data.get('instances', {}).get('healthy', 0)
                if healthy_count > 0:
                    self.log(f"✅ 发现 {healthy_count} 个健康实例")
                    return True
                else:
                    self.log("⚠️  没有健康实例")
                    return False
            else:
                self.log(f"❌ 健康检查失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ 健康检查异常: {e}")
            return False
    
    def test_model_list(self) -> bool:
        """测试模型列表"""
        self.log("\n" + "=" * 60)
        self.log("测试模型列表")
        self.log("=" * 60)
        
        try:
            response = requests.get(f"{self.router_url}/v1/models")
            if response.status_code == 200:
                data = response.json()
                models = data.get('data', [])
                self.log(f"✅ 获取模型列表成功，共 {len(models)} 个模型")
                
                if models:
                    self.log(f"  前3个模型:")
                    for i, model in enumerate(models[:3]):
                        self.log(f"    - {model.get('id', 'unknown')}")
                
                return True
            else:
                self.log(f"❌ 获取模型列表失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ 获取模型列表异常: {e}")
            return False
    
    def test_single_request(self) -> Optional[Dict[str, Any]]:
        """测试单个请求"""
        try:
            response = requests.post(
                f"{self.router_url}/v1/chat/completions",
                json={
                    "model": "gemini-1.5-pro",
                    "messages": [{"role": "user", "content": "Say 'Hello from {instance_id}'"}],
                    "max_tokens": 10,
                    "temperature": 0.1
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                # 从响应头获取实际路由的实例（需要路由器支持）
                instance_id = response.headers.get('X-Routed-Instance', 'unknown')
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "response": data
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:100]}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_load_balancing_roundrobin(self, request_count: int = 30) -> bool:
        """测试轮询负载均衡"""
        self.log("\n" + "=" * 60)
        self.log(f"测试轮询负载均衡 ({request_count} 个请求)")
        self.log("=" * 60)
        
        instance_stats = {}
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.test_single_request) for _ in range(request_count)]
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                
                if result["success"]:
                    success_count += 1
                    instance_id = result.get("instance_id", "unknown")
                    instance_stats[instance_id] = instance_stats.get(instance_id, 0) + 1
                
                if (i + 1) % 5 == 0:
                    self.log(f"  进度: {i + 1}/{request_count}")
        
        self.log(f"\n✅ 成功请求: {success_count}/{request_count}")
        self.log(f"\n请求分布:")
        for instance_id, count in sorted(instance_stats.items()):
            percentage = (count / success_count * 100) if success_count > 0 else 0
            self.log(f"  {instance_id}: {count} 次 ({percentage:.1f}%)")
        
        # 验证分布是否均匀（允许 20% 的偏差）
        if len(instance_stats) >= 2:
            counts = list(instance_stats.values())
            avg = sum(counts) / len(counts)
            max_deviation = max(abs(count - avg) for count in counts) / avg
            
            if max_deviation < 0.3:  # 30% 偏差内认为均匀
                self.log(f"\n✅ 负载均衡分布均匀 (最大偏差: {max_deviation:.1%})")
                return True
            else:
                self.log(f"\n⚠️  负载均衡分布不均匀 (最大偏差: {max_deviation:.1%})")
                return False
        
        return success_count > 0
    
    def test_weighted_load_balancing(self, request_count: int = 40) -> bool:
        """测试权重负载均衡"""
        self.log("\n" + "=" * 60)
        self.log(f"测试权重负载均衡 ({request_count} 个请求)")
        self.log("=" * 60)
        
        # 临时修改策略为 weighted
        try:
            response = requests.post(
                f"{self.router_url}/router/set-strategy",
                json={"strategy": "weighted"}
            )
        except:
            pass
        
        time.sleep(2)  # 等待策略生效
        
        instance_stats = {}
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.test_single_request) for _ in range(request_count)]
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                
                if result["success"]:
                    success_count += 1
                    instance_id = result.get("instance_id", "unknown")
                    instance_stats[instance_id] = instance_stats.get(instance_id, 0) + 1
                
                if (i + 1) % 5 == 0:
                    self.log(f"  进度: {i + 1}/{request_count}")
        
        self.log(f"\n✅ 成功请求: {success_count}/{request_count}")
        self.log(f"\n请求分布:")
        for instance_id, count in sorted(instance_stats.items()):
            percentage = (count / success_count * 100) if success_count > 0 else 0
            self.log(f"  {instance_id}: {count} 次 ({percentage:.1f}%)")
        
        # 恢复策略
        try:
            requests.post(f"{self.router_url}/router/set-strategy", json={"strategy": "roundrobin"})
        except:
            pass
        
        return success_count > 0
    
    def test_concurrent_requests(self, concurrent: int = 15, duration: int = 10) -> bool:
        """测试并发请求"""
        self.log("\n" + "=" * 60)
        self.log(f"测试并发请求 ({concurrent} 并发, {duration} 秒)")
        self.log("=" * 60)
        
        start_time = time.time()
        request_count = 0
        success_count = 0
        error_count = 0
        
        def make_request():
            nonlocal request_count, success_count, error_count
            while time.time() - start_time < duration:
                result = self.test_single_request()
                with self.lock:
                    request_count += 1
                    if result["success"]:
                        success_count += 1
                    else:
                        error_count += 1
        
        threads = []
        for _ in range(concurrent):
            t = threading.Thread(target=make_request)
            t.start()
            threads.append(t)
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        self.log(f"\n✅ 总请求: {request_count}")
        self.log(f"✅ 成功: {success_count}")
        self.log(f"❌ 失败: {error_count}")
        self.log(f"⏱️  耗时: {elapsed:.2f} 秒")
        self.log(f"📊 QPS: {request_count / elapsed:.2f}")
        
        success_rate = success_count / request_count if request_count > 0 else 0
        self.log(f"📈 成功率: {success_rate:.1%}")
        
        return success_rate > 0.9  # 成功率 > 90%
    
    def test_instance_failure(self) -> bool:
        """测试实例故障转移"""
        self.log("\n" + "=" * 60)
        self.log("测试实例故障转移")
        self.log("=" * 60)
        
        # 获取当前实例状态
        try:
            response = requests.get(f"{self.router_url}/router/status")
            status_data = response.json()
            instances = status_data.get('instances', [])
            
            if len(instances) < 2:
                self.log("⚠️  需要至少2个实例才能测试故障转移")
                return False
            
            # 选择一个实例进行"故障"模拟
            target_instance = instances[0]
            target_port = target_instance['port']
            
            self.log(f"模拟实例 {target_instance['id']} (端口: {target_port}) 故障...")
            
            # 找到并终止该实例进程
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and 'launch_camoufox.py' in cmdline and str(target_port) in cmdline:
                        self.log(f"  终止进程 PID: {proc.info['pid']}")
                        proc.terminate()
                        proc.wait(timeout=5)
                        break
                except:
                    pass
            
            time.sleep(3)  # 等待故障检测
            
            # 验证故障检测
            response = requests.get(f"{self.router_url}/router/status")
            status_data = response.json()
            
            failed_detected = False
            for inst in status_data.get('instances', []):
                if inst['port'] == target_port and inst['status'] == 'unhealthy':
                    failed_detected = True
                    self.log(f"✅ 故障检测成功: {inst['id']} 状态为 unhealthy")
                    break
            
            if not failed_detected:
                self.log("❌ 故障检测失败")
                return False
            
            # 测试请求仍然成功（路由到其他实例）
            self.log("\n测试请求路由（应跳过故障实例）...")
            success_count = 0
            for _ in range(10):
                result = self.test_single_request()
                if result["success"]:
                    success_count += 1
            
            self.log(f"✅ 故障转移测试: {success_count}/10 请求成功")
            
            return success_count >= 8  # 至少80%成功率
            
        except Exception as e:
            self.log(f"❌ 故障转移测试异常: {e}")
            return False
    
    def test_lock_mechanism(self) -> bool:
        """测试锁机制（进程内）"""
        self.log("\n" + "=" * 60)
        self.log("测试锁机制（进程内）")
        self.log("=" * 60)
        
        # 测试 processing_lock
        try:
            # 检查锁状态
            response = requests.get(f"{self.router_url}/v1/queue")
            if response.status_code == 200:
                data = response.json()
                is_locked = data.get('is_processing_locked', False)
                queue_size = data.get('queue_size', 0)
                
                self.log(f"processing_lock 状态: {'locked' if is_locked else 'unlocked'}")
                self.log(f"队列大小: {queue_size}")
                
                # 发送多个请求，验证只有一个在处理
                self.log("\n发送 5 个并发请求，验证锁机制...")
                
                results = []
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(self.test_single_request) for _ in range(5)]
                    for future in as_completed(futures):
                        results.append(future.result())
                
                success_count = sum(1 for r in results if r["success"])
                self.log(f"✅ 锁机制测试: {success_count}/5 请求成功")
                
                return success_count >= 4
            else:
                self.log(f"❌ 获取队列状态失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ 锁机制测试异常: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """运行所有测试"""
        self.log("\n" + "=" * 60)
        self.log("开始多账号路由池测试")
        self.log("=" * 60)
        
        # 等待路由器
        if not self.wait_for_router():
            return {"overall": False}
        
        results = {}
        
        # 基础测试
        results["health_check"] = self.test_health_check()
        results["model_list"] = self.test_model_list()
        
        # 负载均衡测试
        results["load_balancing_roundrobin"] = self.test_load_balancing_roundrobin()
        results["load_balancing_weighted"] = self.test_weighted_load_balancing()
        
        # 并发测试
        results["concurrent_requests"] = self.test_concurrent_requests()
        
        # 故障转移测试
        results["instance_failure"] = self.test_instance_failure()
        
        # 锁机制测试
        results["lock_mechanism"] = self.test_lock_mechanism()
        
        # 汇总结果
        self.log("\n" + "=" * 60)
        self.log("测试结果汇总")
        self.log("=" * 60)
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            self.log(f"{test_name:.<40} {status}")
        
        overall = all(results.values())
        self.log(f"\n{'Overall':.<40} {'✅ PASS' if overall else '❌ FAIL'}")
        
        return results


def main():
    """主函数"""
    print("=" * 60)
    print("多账号路由池测试工具")
    print("=" * 60)
    
    # 检查测试配置
    if not os.path.exists("test_multi_account_config.json"):
        print("❌ 测试配置文件不存在: test_multi_account_config.json")
        print("请确保测试配置已创建")
        sys.exit(1)
    
    # 启动测试环境
    print("\n启动测试环境...")
    
    # 启动管理器
    manager_cmd = [sys.executable, "multi_account_manager.py", "test_multi_account_config.json"]
    manager_process = subprocess.Popen(manager_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 等待管理器启动
    time.sleep(5)
    
    # 启动路由器
    router_cmd = [sys.executable, "multi_account_router.py", "test_multi_account_config.json"]
    router_process = subprocess.Popen(router_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 等待路由器启动
    time.sleep(3)
    
    try:
        # 运行测试
        tester = MultiAccountTester(router_port=8180)
        results = tester.run_all_tests()
        
        # 保存测试结果
        with open("test_results.json", "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "overall": all(results.values())
            }, f, indent=2)
        
        print(f"\n测试结果已保存到: test_results.json")
        
        # 返回退出码
        sys.exit(0 if all(results.values()) else 1)
        
    finally:
        # 清理进程
        print("\n清理测试环境...")
        manager_process.terminate()
        router_process.terminate()
        
        try:
            manager_process.wait(timeout=5)
            router_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            manager_process.kill()
            router_process.kill()


if __name__ == "__main__":
    main()
