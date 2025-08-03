"""
请求路由器模块
负责将REST API请求路由到合适的实例
"""
import asyncio
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging

from models import ChatCompletionRequest
from .instance_manager import MultiInstanceManager, InstanceStatus
from .model_manager import ModelManager

class RoutingStrategy(Enum):
    """路由策略枚举"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"
    STICKY_SESSION = "sticky_session"
    MODEL_AFFINITY = "model_affinity"
    PRIMARY_INSTANCE = "primary_instance"  # 优先使用实例1

@dataclass
class RequestContext:
    """请求上下文"""
    request_id: str
    instance_id: Optional[str]
    model_id: Optional[str]
    started_at: float
    client_ip: str
    user_agent: str
    routing_strategy: RoutingStrategy
    retry_count: int = 0
    max_retries: int = 3

class RequestRouter:
    """请求路由器"""
    
    def __init__(self, 
                 instance_manager: MultiInstanceManager,
                 model_manager: ModelManager,
                 logger: Optional[logging.Logger] = None):
        self.instance_manager = instance_manager
        self.model_manager = model_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # 路由配置
        self.default_strategy = RoutingStrategy.LEAST_LOADED
        self.enable_failover = True
        self.request_timeout = 300.0  # 5分钟
        
        # 会话粘性支持
        self.session_affinity: Dict[str, str] = {}  # session_id -> instance_id
        
        # 轮询计数器
        self.round_robin_counter = 0
        
        # 请求历史
        self.request_history: Dict[str, RequestContext] = {}
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'routing_errors': 0,
            'instance_errors': 0,
            'model_errors': 0,
            'average_response_time': 0.0
        }
    
    def set_routing_strategy(self, strategy: RoutingStrategy):
        """设置路由策略"""
        self.default_strategy = strategy
        self.logger.info(f"路由策略已设置为: {strategy.value}")
    
    def enable_session_affinity(self, session_id: str, instance_id: str):
        """启用会话粘性"""
        self.session_affinity[session_id] = instance_id
        self.logger.debug(f"会话粘性已启用: {session_id} -> {instance_id}")
    
    def disable_session_affinity(self, session_id: str):
        """禁用会话粘性"""
        if session_id in self.session_affinity:
            del self.session_affinity[session_id]
            self.logger.debug(f"会话粘性已禁用: {session_id}")
    
    def _select_instance_round_robin(self, available_instances: List[str]) -> Optional[str]:
        """轮询选择实例"""
        if not available_instances:
            return None
        
        instance_id = available_instances[self.round_robin_counter % len(available_instances)]
        self.round_robin_counter += 1
        return instance_id
    
    def _select_instance_least_loaded(self, available_instances: List[str]) -> Optional[str]:
        """选择负载最轻的实例"""
        if not available_instances:
            return None
        
        best_instance = None
        best_load = float('inf')
        
        for instance_id in available_instances:
            state = self.instance_manager.get_instance_state(instance_id)
            if state:
                load = state.active_requests / state.config.max_concurrent_requests
                if load < best_load:
                    best_load = load
                    best_instance = instance_id
        
        return best_instance or available_instances[0]
    
    def _select_instance_random(self, available_instances: List[str]) -> Optional[str]:
        """随机选择实例"""
        if not available_instances:
            return None
        
        import random
        return random.choice(available_instances)
    
    def _select_instance_model_affinity(self, available_instances: List[str], model_id: str) -> Optional[str]:
        """基于模型亲和性选择实例"""
        if not available_instances:
            return None
        
        # 优先选择当前正在使用相同模型的实例
        for instance_id in available_instances:
            state = self.instance_manager.get_instance_state(instance_id)
            if state and state.current_model_id == model_id:
                return instance_id
        
        # 如果没有相同模型的实例，使用最少负载策略
        return self._select_instance_least_loaded(available_instances)
    
    def _select_instance_primary(self, available_instances: List[str]) -> Optional[str]:
        """优先选择主实例（实例1）"""
        if not available_instances:
            return None
        
        # 查找包含 'instance_1' 的实例ID
        primary_candidates = [inst for inst in available_instances if 'instance_1' in inst]
        
        if primary_candidates:
            # 如果有多个instance_1的候选，选择第一个
            primary_instance = primary_candidates[0]
            
            # 检查主实例是否过载
            state = self.instance_manager.get_instance_state(primary_instance)
            if state and state.status == InstanceStatus.READY:
                load = state.active_requests / state.config.max_concurrent_requests
                
                # 如果主实例负载小于80%，优先使用
                if load < 0.8:
                    self.logger.info(f"使用主实例: {primary_instance} (负载: {load:.2%})")
                    return primary_instance
                else:
                    self.logger.info(f"主实例负载过高 ({load:.2%})，切换到备用实例")
        
        # 如果主实例不可用或过载，使用最少负载策略
        return self._select_instance_least_loaded(available_instances)
    
    def _select_instance_by_strategy(self, 
                                   available_instances: List[str], 
                                   strategy: RoutingStrategy,
                                   model_id: Optional[str] = None,
                                   session_id: Optional[str] = None) -> Optional[str]:
        """根据策略选择实例"""
        
        # 会话粘性优先
        if session_id and session_id in self.session_affinity:
            sticky_instance = self.session_affinity[session_id]
            if sticky_instance in available_instances:
                return sticky_instance
        
        # 根据策略选择
        if strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_instance_round_robin(available_instances)
        elif strategy == RoutingStrategy.LEAST_LOADED:
            return self._select_instance_least_loaded(available_instances)
        elif strategy == RoutingStrategy.RANDOM:
            return self._select_instance_random(available_instances)
        elif strategy == RoutingStrategy.MODEL_AFFINITY and model_id:
            return self._select_instance_model_affinity(available_instances, model_id)
        elif strategy == RoutingStrategy.PRIMARY_INSTANCE:
            return self._select_instance_primary(available_instances)
        else:
            # 默认使用最少负载
            return self._select_instance_least_loaded(available_instances)
    
    async def route_request(self, 
                          request: ChatCompletionRequest,
                          client_ip: str = "",
                          user_agent: str = "",
                          session_id: Optional[str] = None,
                          preferred_instance: Optional[str] = None,
                          strategy: Optional[RoutingStrategy] = None) -> Optional[str]:
        """路由请求到合适的实例"""
        
        request_id = str(uuid.uuid4())
        model_id = request.model if request.model else None
        current_strategy = strategy or self.default_strategy
        
        # 创建请求上下文
        context = RequestContext(
            request_id=request_id,
            instance_id=None,
            model_id=model_id,
            started_at=time.time(),
            client_ip=client_ip,
            user_agent=user_agent,
            routing_strategy=current_strategy
        )
        
        self.request_history[request_id] = context
        self.stats['total_requests'] += 1
        
        try:
            # 如果指定了首选实例，优先使用
            if preferred_instance:
                if await self._try_route_to_instance(preferred_instance, model_id, context):
                    return preferred_instance
            
            # 获取可用实例
            available_instances = self.instance_manager.get_available_instances()
            
            if not available_instances:
                self.logger.warning(f"没有可用实例处理请求: {request_id}")
                self.stats['routing_errors'] += 1
                return None
            
            # 过滤支持请求模型的实例
            if model_id:
                filtered_instances = []
                for instance_id in available_instances:
                    if self.model_manager.is_model_available_for_instance(instance_id, model_id):
                        filtered_instances.append(instance_id)
                
                if not filtered_instances:
                    self.logger.warning(f"没有实例支持模型 {model_id} 的请求: {request_id}")
                    self.stats['model_errors'] += 1
                    return None
                
                available_instances = filtered_instances
            
            # 选择实例
            selected_instance = self._select_instance_by_strategy(
                available_instances, 
                current_strategy, 
                model_id, 
                session_id
            )
            
            if not selected_instance:
                self.logger.error(f"实例选择失败: {request_id}")
                self.stats['routing_errors'] += 1
                return None
            
            # 尝试路由到选定实例
            if await self._try_route_to_instance(selected_instance, model_id, context):
                return selected_instance
            
            # 如果失败且启用故障转移，尝试其他实例
            if self.enable_failover:
                for instance_id in available_instances:
                    if instance_id != selected_instance:
                        if await self._try_route_to_instance(instance_id, model_id, context):
                            self.logger.info(f"故障转移成功: {request_id} -> {instance_id}")
                            return instance_id
            
            self.logger.error(f"所有实例都无法处理请求: {request_id}")
            self.stats['routing_errors'] += 1
            return None
            
        except Exception as e:
            self.logger.error(f"路由请求时发生错误: {request_id}, 错误: {e}")
            self.stats['routing_errors'] += 1
            return None
    
    async def _try_route_to_instance(self, instance_id: str, model_id: Optional[str], context: RequestContext) -> bool:
        """尝试将请求路由到指定实例"""
        try:
            # 检查实例状态
            state = self.instance_manager.get_instance_state(instance_id)
            if not state or state.status != InstanceStatus.READY:
                return False
            
            # 检查模型支持
            if model_id and not self.model_manager.is_model_available_for_instance(instance_id, model_id):
                return False
            
            # 尝试获取实例锁
            if await self.instance_manager.acquire_instance_lock(instance_id):
                context.instance_id = instance_id
                self.logger.debug(f"请求路由成功: {context.request_id} -> {instance_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"路由到实例 {instance_id} 时发生错误: {e}")
            return False
    
    async def complete_request(self, request_id: str, success: bool, response_time: float):
        """完成请求处理"""
        if request_id not in self.request_history:
            return
        
        context = self.request_history[request_id]
        
        # 释放实例锁
        if context.instance_id:
            await self.instance_manager.release_instance_lock(context.instance_id)
        
        # 更新统计信息
        if success:
            self.stats['successful_requests'] += 1
        else:
            self.stats['failed_requests'] += 1
        
        # 更新平均响应时间
        total_requests = self.stats['successful_requests'] + self.stats['failed_requests']
        if total_requests > 0:
            current_avg = self.stats['average_response_time']
            self.stats['average_response_time'] = (current_avg * (total_requests - 1) + response_time) / total_requests
        
        # 清理请求历史（保留最近1000个请求）
        if len(self.request_history) > 1000:
            oldest_requests = sorted(self.request_history.keys(), 
                                   key=lambda k: self.request_history[k].started_at)[:100]
            for old_request_id in oldest_requests:
                del self.request_history[old_request_id]
        
        self.logger.debug(f"请求完成: {request_id}, 成功: {success}, 响应时间: {response_time:.2f}s")
    
    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """获取请求状态"""
        if request_id not in self.request_history:
            return None
        
        context = self.request_history[request_id]
        return {
            'request_id': context.request_id,
            'instance_id': context.instance_id,
            'model_id': context.model_id,
            'started_at': context.started_at,
            'client_ip': context.client_ip,
            'user_agent': context.user_agent,
            'routing_strategy': context.routing_strategy.value,
            'retry_count': context.retry_count
        }
    
    def get_active_requests(self) -> List[Dict[str, Any]]:
        """获取活跃请求列表"""
        active_requests = []
        current_time = time.time()
        
        for request_id, context in self.request_history.items():
            if context.instance_id and (current_time - context.started_at) < self.request_timeout:
                active_requests.append({
                    'request_id': context.request_id,
                    'instance_id': context.instance_id,
                    'model_id': context.model_id,
                    'started_at': context.started_at,
                    'duration': current_time - context.started_at,
                    'client_ip': context.client_ip,
                    'routing_strategy': context.routing_strategy.value
                })
        
        return active_requests
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        # 按实例统计
        instance_stats = {}
        for context in self.request_history.values():
            if context.instance_id:
                if context.instance_id not in instance_stats:
                    instance_stats[context.instance_id] = {
                        'total_requests': 0,
                        'active_requests': 0,
                        'average_response_time': 0.0
                    }
                instance_stats[context.instance_id]['total_requests'] += 1
        
        # 按模型统计
        model_stats = {}
        for context in self.request_history.values():
            if context.model_id:
                if context.model_id not in model_stats:
                    model_stats[context.model_id] = 0
                model_stats[context.model_id] += 1
        
        # 按策略统计
        strategy_stats = {}
        for context in self.request_history.values():
            strategy = context.routing_strategy.value
            if strategy not in strategy_stats:
                strategy_stats[strategy] = 0
            strategy_stats[strategy] += 1
        
        # 计算可用实例数量
        available_instances = len(self.instance_manager.get_available_instances())
        
        return {
            'global_stats': self.stats,
            'instance_stats': instance_stats,
            'model_stats': model_stats,
            'strategy_stats': strategy_stats,
            'active_requests_count': len(self.get_active_requests()),
            'session_affinity_count': len(self.session_affinity),
            'available_instances': available_instances
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'routing_errors': 0,
            'instance_errors': 0,
            'model_errors': 0,
            'average_response_time': 0.0
        }
        self.request_history.clear()
        self.logger.info("路由统计信息已重置")
    
    def cleanup_expired_requests(self):
        """清理过期请求"""
        current_time = time.time()
        expired_requests = []
        
        for request_id, context in self.request_history.items():
            if (current_time - context.started_at) > self.request_timeout:
                expired_requests.append(request_id)
        
        for request_id in expired_requests:
            context = self.request_history[request_id]
            if context.instance_id:
                # 异步释放锁
                asyncio.create_task(self.instance_manager.release_instance_lock(context.instance_id))
            del self.request_history[request_id]
        
        if expired_requests:
            self.logger.info(f"清理了 {len(expired_requests)} 个过期请求")
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取路由器健康状态"""
        current_time = time.time()
        
        # 检查活跃请求
        active_count = len(self.get_active_requests())
        
        # 检查实例状态
        available_instances = self.instance_manager.get_available_instances()
        total_instances = len(self.instance_manager.instances)
        
        # 计算成功率
        total_requests = self.stats['successful_requests'] + self.stats['failed_requests']
        success_rate = (self.stats['successful_requests'] / total_requests * 100) if total_requests > 0 else 0
        
        # 健康状态评估
        health_status = "healthy"
        if len(available_instances) == 0:
            health_status = "critical"
        elif len(available_instances) < total_instances * 0.5:
            health_status = "warning"
        elif success_rate < 90:
            health_status = "degraded"
        
        return {
            'status': health_status,
            'total_instances': total_instances,
            'available_instances': len(available_instances),
            'active_requests': active_count,
            'success_rate': success_rate,
            'average_response_time': self.stats['average_response_time'],
            'total_requests': total_requests,
            'routing_errors': self.stats['routing_errors'],
            'timestamp': current_time
        }