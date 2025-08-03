#!/usr/bin/env python3
"""
多账号实例启动脚本
支持同时启动多个AI Studio账号实例
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
import signal

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from multi_instance.launcher import MultiInstanceLauncher
from multi_instance.account_manager import AccountManager
from multi_instance.instance_manager import MultiInstanceManager


def setup_logging(log_level: str = "INFO"):
    """设置日志配置"""
    # 将日志级别字符串转换为logging常量
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('multi_instance.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def signal_handler(signum, frame, launcher, logger):
    """信号处理函数"""
    logger.info(f"收到信号 {signum}，正在停止所有实例...")
    launcher.cleanup_all_instances()
    logger.info("所有实例已停止")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description='启动多账号AI Studio实例')
    parser.add_argument('--auth-dir', default='auth_profiles/multi', 
                       help='认证文件目录')
    parser.add_argument('--mode', default='headless', 
                       choices=['headless', 'headful'],
                       help='启动模式')
    parser.add_argument('--proxy', help='代理配置')
    parser.add_argument('--os', default='linux', 
                       choices=['linux', 'windows', 'mac'],
                       help='模拟操作系统')
    parser.add_argument('--max-concurrent', type=int, default=3,
                       help='最大并发启动实例数')
    parser.add_argument('--startup-delay', type=int, default=2,
                       help='实例启动间隔(秒)')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='日志级别')
    parser.add_argument('--refresh-interval', type=int, default=0,
                       help='账号刷新间隔(秒)，0表示不刷新')
    
    args = parser.parse_args()
    
    logger = setup_logging(args.log_level)
    logger.info("开始启动多账号实例...")
    
    try:
        # 1. 创建账号管理器
        account_manager = AccountManager(args.auth_dir, logger)
        accounts = account_manager.list_accounts()
        
        if not accounts:
            logger.error(f"在目录 {args.auth_dir} 中未找到认证文件")
            return 1
        
        logger.info(f"发现 {len(accounts)} 个账号: {', '.join(accounts)}")
        
        # 2. 创建实例管理器
        instance_manager = MultiInstanceManager(logger=logger)
        
        # 3. 自动创建实例配置
        new_instances = instance_manager.auto_create_instances()
        if new_instances:
            logger.info(f"自动创建了 {len(new_instances)} 个新实例配置")
        
        # 4. 创建启动器
        launcher = MultiInstanceLauncher(logger)
        
        # 5. 发现认证配置
        profiles = launcher.discover_auth_profiles(args.auth_dir)
        if not profiles:
            logger.error(f"未在目录 {args.auth_dir} 中发现有效的认证配置")
            return 1
        
        # 6. 创建实例配置
        configs = launcher.create_instance_configs(
            profiles, 
            launch_mode=args.mode,
            proxy_config=args.proxy,
            simulated_os=args.os
        )
        
        # 7. 启动所有实例
        endpoints = launcher.launch_all_instances(
            configs,
            max_concurrent=args.max_concurrent,
            startup_delay=args.startup_delay
        )
        
        if not endpoints:
            logger.error("未能启动任何实例")
            return 1
        
        logger.info(f"成功启动 {len(endpoints)} 个实例:")
        for instance_id, ws_endpoint in endpoints.items():
            logger.info(f"  - {instance_id}: {ws_endpoint}")
        
        # 8. 设置信号处理
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, launcher, logger))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, launcher, logger))
        
        # 9. 保持运行
        logger.info("所有实例已启动，按 Ctrl+C 停止...")
        
        try:
            # 等待用户中断或定期刷新账号
            import time
            last_refresh = time.time()
            while True:
                time.sleep(1)
                
                # 检查是否需要刷新账号
                if args.refresh_interval > 0 and \
                   (time.time() - last_refresh) > args.refresh_interval:
                    logger.info("定期刷新账号列表")
                    account_manager.refresh_accounts()
                    # 重新创建实例配置
                    new_instances = instance_manager.auto_create_instances()
                    if new_instances:
                        logger.info(f"刷新后创建了 {len(new_instances)} 个新实例配置")
                    last_refresh = time.time()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在停止所有实例...")
            launcher.cleanup_all_instances()
            logger.info("所有实例已停止")
        
        return 0
        
    except Exception as e:
        logger.error(f"启动过程中发生错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())