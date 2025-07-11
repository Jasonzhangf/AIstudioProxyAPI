#!/usr/bin/env python3
"""
快速检查多实例端口状态
Quick check for multi-instance port status
"""

import os
import sys
from instance_manager import InstanceManager

def main():
    """主函数"""
    print("🔍 检查多实例端口状态")
    print("=" * 50)
    
    # 创建实例管理器
    manager = InstanceManager("auth_profiles")
    
    # 发现认证文件
    auth_files = manager.discover_auth_profiles()
    
    if not auth_files:
        print("❌ 未发现认证文件")
        return
    
    print(f"📋 发现 {len(auth_files)} 个认证文件:\n")
    
    occupied_ports = []
    available_ports = []
    
    for i, auth_file in enumerate(auth_files):
        filename = os.path.basename(auth_file)
        port = manager._get_assigned_port(auth_file)
        pids = manager.find_pids_on_port(port)
        
        if pids:
            status = "🔴 占用"
            pid_info = f"PID: {pids}"
            occupied_ports.append((filename, port, pids))
        else:
            status = "🟢 可用"
            pid_info = ""
            available_ports.append((filename, port))
        
        print(f"{i+1:2d}. {filename:<30} 端口 {port:<6} {status} {pid_info}")
    
    print(f"\n📊 统计:")
    print(f"   总端口数: {len(auth_files)}")
    print(f"   🟢 可用: {len(available_ports)}")
    print(f"   🔴 占用: {len(occupied_ports)}")
    
    if occupied_ports:
        print(f"\n⚠️  被占用的端口:")
        for filename, port, pids in occupied_ports:
            print(f"   端口 {port}: {filename} (PID: {pids})")
        
        print(f"\n💡 清理建议:")
        print(f"   python cleanup_ports.py --all")
        print(f"   或者手动清理: python cleanup_ports.py --port", end="")
        for _, port, _ in occupied_ports:
            print(f" {port}", end="")
        print()
    else:
        print(f"\n✅ 所有端口都可用，可以直接启动多实例模式")

if __name__ == "__main__":
    main()