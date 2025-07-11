#!/usr/bin/env python3
"""
端口清理工具脚本
Port cleanup utility script
"""

import os
import sys
import argparse
from instance_manager import InstanceManager

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="清理多实例端口工具")
    parser.add_argument("--auth-dir", default="auth_profiles", 
                       help="认证文件目录 (默认: auth_profiles)")
    parser.add_argument("--base-port", type=int, default=9222,
                       help="基础端口号 (默认: 9222)")
    parser.add_argument("--all", action="store_true",
                       help="清理所有已分配的端口")
    parser.add_argument("--port", type=int, nargs="+",
                       help="清理指定端口")
    parser.add_argument("--list", action="store_true",
                       help="列出端口分配情况")
    
    args = parser.parse_args()
    
    # 创建实例管理器
    manager = InstanceManager(args.auth_dir, args.base_port)
    
    if args.list:
        # 列出端口分配
        print("📋 端口分配情况:")
        auth_files = manager.discover_auth_profiles()
        
        if not auth_files:
            print("   未发现认证文件")
            return
        
        for auth_file in auth_files:
            port = manager._get_assigned_port(auth_file)
            filename = os.path.basename(auth_file)
            pids = manager.find_pids_on_port(port)
            status = "🔴 被占用" if pids else "🟢 可用"
            pid_info = f" (PID: {pids})" if pids else ""
            print(f"   {filename} -> 端口 {port} {status}{pid_info}")
        
        return
    
    if args.all:
        # 清理所有分配的端口
        print("🔧 清理所有已分配的端口...")
        auth_files = manager.discover_auth_profiles()
        
        if not auth_files:
            print("   未发现认证文件")
            return
        
        for auth_file in auth_files:
            port = manager._get_assigned_port(auth_file)
            filename = os.path.basename(auth_file)
            print(f"   清理 {filename} 的端口 {port}")
            manager.cleanup_port(port)
        
        print("✅ 所有端口清理完成")
        return
    
    if args.port:
        # 清理指定端口
        print(f"🔧 清理指定端口: {args.port}")
        
        for port in args.port:
            print(f"   清理端口 {port}")
            manager.cleanup_port(port)
        
        print("✅ 指定端口清理完成")
        return
    
    # 默认行为：显示帮助
    parser.print_help()

if __name__ == "__main__":
    main()