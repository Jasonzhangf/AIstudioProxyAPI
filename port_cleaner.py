#!/usr/bin/env python3
"""
完整的端口检查和清理工具
"""
import os
import sys
import time
import subprocess
import socket
import signal
import psutil
from typing import List, Dict, Set

class PortCleaner:
    """端口清理工具"""
    
    def __init__(self):
        self.api_ports = [2048, 3120]  # API服务器端口
        self.websocket_ports = [9230, 9240, 9269]  # WebSocket端口
        self.all_ports = self.api_ports + self.websocket_ports
        
    def find_processes_on_port(self, port: int) -> List[Dict]:
        """查找占用指定端口的进程"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    for conn in proc.connections():
                        if conn.laddr.port == port:
                            processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"⚠️ 查找端口 {port} 进程时出错: {e}")
        
        return processes
    
    def is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('127.0.0.1', port))
                return True
        except OSError:
            return False
    
    def kill_process(self, pid: int) -> bool:
        """终止进程"""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            
            # 等待进程优雅退出
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # 强制杀死进程
                proc.kill()
                proc.wait(timeout=3)
            
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"⚠️ 无法终止进程 {pid}: {e}")
            return False
    
    def clean_port(self, port: int) -> bool:
        """清理指定端口"""
        print(f"🔍 检查端口 {port}...")
        
        if self.is_port_available(port):
            print(f"✅ 端口 {port} 可用")
            return True
        
        # 查找占用端口的进程
        processes = self.find_processes_on_port(port)
        if not processes:
            print(f"❌ 端口 {port} 被占用但未找到进程")
            return False
        
        print(f"⚠️ 端口 {port} 被以下进程占用:")
        for proc in processes:
            print(f"   PID: {proc['pid']}, 名称: {proc['name']}, 命令: {proc['cmdline'][:80]}...")
        
        # 终止所有占用端口的进程
        success_count = 0
        for proc in processes:
            if self.kill_process(proc['pid']):
                success_count += 1
                print(f"✅ 已终止进程 {proc['pid']}")
            else:
                print(f"❌ 无法终止进程 {proc['pid']}")
        
        # 等待端口释放
        time.sleep(2)
        
        # 再次检查端口
        if self.is_port_available(port):
            print(f"✅ 端口 {port} 清理成功")
            return True
        else:
            print(f"❌ 端口 {port} 清理失败")
            return False
    
    def clean_all_ports(self) -> bool:
        """清理所有相关端口"""
        print("🧹 开始清理所有端口...")
        
        success_count = 0
        for port in self.all_ports:
            if self.clean_port(port):
                success_count += 1
        
        print(f"📊 端口清理结果: {success_count}/{len(self.all_ports)} 个端口清理成功")
        return success_count == len(self.all_ports)
    
    def clean_related_processes(self) -> bool:
        """清理相关进程（不依赖端口）"""
        print("🧹 清理相关进程...")
        
        # 查找相关进程
        processes_to_kill = []
        process_names = ['uvicorn', 'python']
        keywords = ['launch_camoufox', 'server.py', 'camoufox']
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if not proc.info['cmdline']:
                        continue
                    
                    cmdline = ' '.join(proc.info['cmdline'])
                    
                    # 检查是否是相关进程
                    if any(keyword in cmdline for keyword in keywords):
                        processes_to_kill.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline
                        })
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"⚠️ 查找相关进程时出错: {e}")
        
        if not processes_to_kill:
            print("✅ 未发现相关进程")
            return True
        
        print(f"🎯 找到 {len(processes_to_kill)} 个相关进程:")
        for proc in processes_to_kill:
            print(f"   PID: {proc['pid']}, 名称: {proc['name']}, 命令: {proc['cmdline'][:80]}...")
        
        # 终止相关进程
        success_count = 0
        for proc in processes_to_kill:
            if self.kill_process(proc['pid']):
                success_count += 1
                print(f"✅ 已终止进程 {proc['pid']}")
            else:
                print(f"❌ 无法终止进程 {proc['pid']}")
        
        print(f"📊 进程清理结果: {success_count}/{len(processes_to_kill)} 个进程清理成功")
        return success_count == len(processes_to_kill)
    
    def full_cleanup(self) -> bool:
        """完整清理"""
        print("🚀 开始完整清理...")
        
        # 先清理相关进程
        process_cleanup = self.clean_related_processes()
        
        # 等待进程完全退出
        time.sleep(3)
        
        # 再清理端口
        port_cleanup = self.clean_all_ports()
        
        success = process_cleanup and port_cleanup
        
        if success:
            print("✅ 完整清理成功")
        else:
            print("❌ 完整清理失败")
        
        return success

def main():
    """主函数"""
    cleaner = PortCleaner()
    return cleaner.full_cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)