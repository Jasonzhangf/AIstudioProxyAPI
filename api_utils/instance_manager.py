"""
实例管理模块
负责实例状态管理、错误恢复和页面重新初始化
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger("AIStudioProxyServer")

@dataclass
class InstanceStatus:
    """实例状态信息"""
    instance_id: int
    is_disabled: bool = False
    last_error_time: Optional[float] = None
    error_count: int = 0
    disabled_since_model: Optional[str] = None
    needs_reinit: bool = False
    last_reinit_attempt: Optional[float] = None

class InstanceManager:
    """实例管理器"""
    
    def __init__(self):
        self.instance_statuses: Dict[int, InstanceStatus] = {}
        self.reinit_lock = asyncio.Lock()
        self.max_error_count = 2  # 最大错误次数
        self.error_window = 300   # 错误窗口期（5分钟）
        self.reinit_cooldown = 60 # 重新初始化冷却期（1分钟）
        
    def get_instance_status(self, instance_id: int) -> InstanceStatus:
        """获取实例状态"""
        if instance_id not in self.instance_statuses:
            self.instance_statuses[instance_id] = InstanceStatus(instance_id=instance_id)
        return self.instance_statuses[instance_id]
    
    def is_instance_available(self, instance_id: int) -> bool:
        """检查实例是否可用"""
        status = self.get_instance_status(instance_id)
        return not status.is_disabled
    
    def get_available_instances(self) -> List[int]:
        """获取所有可用的实例ID"""
        import server
        
        if not getattr(server, 'is_multi_instance_mode', False):
            return [1]  # 单实例模式
        
        # 多实例模式：使用正常的多实例逻辑
        total_instances = len(getattr(server, 'multi_instance_pages', []))
        if total_instances == 0:
            return [1]
        
        # 过滤掉被禁用的实例
        all_instances = list(range(1, total_instances + 1))
        available_instances = [
            inst_id for inst_id in all_instances 
            if self.is_instance_available(inst_id)
        ]
        
        # 如果所有实例都被禁用，返回第一个实例（紧急模式）
        if not available_instances:
            logger.warning("所有实例都被禁用，返回实例1作为紧急模式")
            return [1]
        
        return available_instances
    
    async def report_generation_error(self, instance_id: int, req_id: str, current_model: str) -> bool:
        """
        报告生成错误
        返回True表示需要切换到下一个实例，False表示可以继续使用当前实例
        """
        status = self.get_instance_status(instance_id)
        current_time = time.time()
        
        # 记录错误
        status.last_error_time = current_time
        status.error_count += 1
        
        logger.warning(f"[{req_id}] 实例 {instance_id} 报告生成错误 (错误次数: {status.error_count})")
        
        # 检查是否需要页面重新初始化
        if status.error_count == 1 and not status.needs_reinit:
            logger.info(f"[{req_id}] 实例 {instance_id} 首次错误，标记为需要重新初始化")
            status.needs_reinit = True
            return False  # 先尝试重新初始化
        
        # 检查是否需要禁用实例
        if status.error_count >= self.max_error_count:
            logger.warning(f"[{req_id}] 实例 {instance_id} 错误次数达到上限，禁用实例直到模型改变")
            self.disable_instance(instance_id, current_model)
            return True  # 切换到下一个实例
        
        return False  # 继续使用当前实例
    
    def disable_instance(self, instance_id: int, current_model: str):
        """禁用实例直到模型改变"""
        status = self.get_instance_status(instance_id)
        status.is_disabled = True
        status.disabled_since_model = current_model
        
        logger.warning(f"实例 {instance_id} 已被禁用，直到模型从 '{current_model}' 改变")
    
    def on_model_change(self, new_model: str):
        """当模型改变时，重新启用被禁用的实例"""
        enabled_count = 0
        
        for instance_id, status in self.instance_statuses.items():
            if status.is_disabled and status.disabled_since_model != new_model:
                logger.info(f"模型改变为 '{new_model}'，重新启用实例 {instance_id}")
                status.is_disabled = False
                status.disabled_since_model = None
                status.error_count = 0
                status.needs_reinit = False
                enabled_count += 1
        
        if enabled_count > 0:
            logger.info(f"由于模型改变，共重新启用了 {enabled_count} 个实例")
    
    async def should_reinit_page(self, instance_id: int) -> bool:
        """检查是否应该重新初始化页面"""
        status = self.get_instance_status(instance_id)
        
        if not status.needs_reinit:
            return False
        
        # 检查冷却期
        if status.last_reinit_attempt:
            time_since_last = time.time() - status.last_reinit_attempt
            if time_since_last < self.reinit_cooldown:
                logger.debug(f"实例 {instance_id} 重新初始化在冷却期中，还需等待 {self.reinit_cooldown - time_since_last:.1f} 秒")
                return False
        
        return True
    
    async def perform_page_reinit(self, instance_id: int, req_id: str) -> bool:
        """执行页面重新初始化"""
        async with self.reinit_lock:
            status = self.get_instance_status(instance_id)
            status.last_reinit_attempt = time.time()
            
            try:
                logger.info(f"[{req_id}] 开始重新初始化实例 {instance_id} 的页面")
                
                # 获取目标页面
                page = await self._get_instance_page(instance_id)
                if not page:
                    logger.error(f"[{req_id}] 无法获取实例 {instance_id} 的页面")
                    return False
                
                # 导航到初始化页面
                await page.goto("https://aistudio.google.com/prompts/new_chat", timeout=30000)
                logger.info(f"[{req_id}] 实例 {instance_id} 已导航到新聊天页面")
                
                # 等待页面加载完成
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                # 验证页面是否正确加载
                from config import PROMPT_TEXTAREA_SELECTOR
                textarea_locator = page.locator(PROMPT_TEXTAREA_SELECTOR)
                await textarea_locator.wait_for(state="visible", timeout=10000)
                
                logger.info(f"[{req_id}] ✅ 实例 {instance_id} 页面重新初始化成功")
                
                # 标记重新初始化完成
                status.needs_reinit = False
                status.error_count = 0  # 重置错误计数
                
                return True
                
            except Exception as e:
                logger.error(f"[{req_id}] ❌ 实例 {instance_id} 页面重新初始化失败: {e}")
                return False
    
    async def _get_instance_page(self, instance_id: int):
        """获取指定实例的页面对象"""
        import server
        
        # 默认使用主实例
        if instance_id == 1 or not getattr(server, 'is_multi_instance_mode', False):
            return getattr(server, 'page_instance', None)
        
        # 使用多实例中的指定实例
        multi_instance_pages = getattr(server, 'multi_instance_pages', [])
        if multi_instance_pages and instance_id <= len(multi_instance_pages):
            return multi_instance_pages[instance_id - 1]
        
        # 如果指定实例不存在，回退到主实例
        return getattr(server, 'page_instance', None)
    
    def reset_instance_status(self, instance_id: int):
        """重置实例状态（用于测试或手动重置）"""
        if instance_id in self.instance_statuses:
            status = self.instance_statuses[instance_id]
            status.is_disabled = False
            status.error_count = 0
            status.needs_reinit = False
            status.disabled_since_model = None
            logger.info(f"实例 {instance_id} 状态已重置")
    
    def get_instance_statistics(self) -> Dict:
        """获取实例统计信息"""
        stats = {
            "total_instances": len(self.instance_statuses),
            "available_instances": len(self.get_available_instances()),
            "disabled_instances": len([s for s in self.instance_statuses.values() if s.is_disabled]),
            "instances_needing_reinit": len([s for s in self.instance_statuses.values() if s.needs_reinit]),
            "instance_details": {}
        }
        
        for instance_id, status in self.instance_statuses.items():
            stats["instance_details"][instance_id] = {
                "is_disabled": status.is_disabled,
                "error_count": status.error_count,
                "needs_reinit": status.needs_reinit,
                "disabled_since_model": status.disabled_since_model,
                "last_error_time": status.last_error_time,
                "last_reinit_attempt": status.last_reinit_attempt
            }
        
        return stats

# 全局实例管理器
instance_manager = InstanceManager()