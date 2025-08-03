"""
智能请求路由器
负责2048端口的请求接收、实例选择和请求转发
"""
import asyncio
import time
import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from fastapi import Request, HTTPException
from models import ChatCompletionRequest
from .smart_instance_manager import SmartInstanceManager, InstanceStatus

class RoutingStrategy(Enum):
    """路由策略"""
    LEAST_LOADED = "least_loaded"
    ROUND_ROBIN = "round_robin"
    PRIMARY_FIRST = "primary_first"  # 优先使用主实例
    RANDOM = "random"

@dataclass
class RequestContext:
    """请求上下文"""
    request_id: str
    instance_id: Optional[str]
    model_id: Optional[str]
    started_at: float
    client_ip: str
    user_agent: str
    original_request: ChatCompletionRequest
    http_request: Request
    retry_count: int = 0
    max_retries: int = 2

class SmartRequestRouter:
    """智能请求路由器"""
    
    def __init__(self, 
                 instance_manager: SmartInstanceManager,
                 logger: Optional[logging.Logger] = None):
        
        self.instance_manager = instance_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # 路由配置
        self.routing_strategy = RoutingStrategy.PRIMARY_FIRST
        self.enable_failover = True
        self.request_timeout = 300.0  # 5分钟
        
        # 请求跟踪
        self.active_requests: Dict[str, RequestContext] = {}
        self.request_history: List[RequestContext] = []
        
        # 轮询计数器
        self.round_robin_counter = 0
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'routing_errors': 0,
            'average_response_time': 0.0
        }
    
    async def route_request(self, 
                          request: ChatCompletionRequest, 
                          http_request: Request) -> Tuple[str, Any]:
        """
        路由请求到合适的实例
        返回: (request_id, response)
        """
        request_id = str(uuid.uuid4())
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent", "unknown")
        
        # 创建请求上下文
        context = RequestContext(
            request_id=request_id,
            instance_id=None,
            model_id=request.model,
            started_at=time.time(),
            client_ip=client_ip,
            user_agent=user_agent,
            original_request=request,
            http_request=http_request
        )
        
        self.active_requests[request_id] = context
        self.stats['total_requests'] += 1
        
        self.logger.info(f"[{request_id}] 收到请求，模型: {request.model}")
        
        try:
            # 选择实例
            instance_id = await self._select_instance(context)
            if not instance_id:
                raise HTTPException(
                    status_code=503, 
                    detail=f"[{request_id}] 服务当前不可用。请稍后重试。",
                    headers={"Retry-After": "30"}
                )
            
            context.instance_id = instance_id
            self.logger.info(f"[{request_id}] 路由到实例: {instance_id}")
            
            # 获取实例锁
            if not await self._acquire_instance_lock(instance_id):
                raise HTTPException(
                    status_code=503,
                    detail=f"[{request_id}] 实例繁忙，请稍后重试。"
                )
            
            try:
                # 处理请求
                response = await self._process_request_on_instance(context)
                
                # 记录成功
                self._record_success(context)
                
                return request_id, response
                
            finally:
                # 释放实例锁
                await self._release_instance_lock(instance_id)
                
        except HTTPException:
            self._record_failure(context)
            raise
        except Exception as e:
            self.logger.error(f"[{request_id}] 处理请求时发生错误: {e}")
            self._record_failure(context)
            raise HTTPException(
                status_code=500,
                detail=f"[{request_id}] 服务器内部错误"
            )
        finally:
            # 清理请求上下文
            if request_id in self.active_requests:
                del self.active_requests[request_id]
            
            # 保留历史记录（限制数量）
            self.request_history.append(context)
            if len(self.request_history) > 1000:
                self.request_history = self.request_history[-500:]
    
    async def _select_instance(self, context: RequestContext) -> Optional[str]:
        """选择合适的实例"""
        available_instances = self.instance_manager.get_available_instances()
        
        if not available_instances:
            self.logger.warning(f"[{context.request_id}] 没有可用实例")
            return None
        
        # 根据策略选择实例
        if self.routing_strategy == RoutingStrategy.PRIMARY_FIRST:
            return self._select_primary_first(available_instances)
        elif self.routing_strategy == RoutingStrategy.LEAST_LOADED:
            return self._select_least_loaded(available_instances)
        elif self.routing_strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_instances)
        elif self.routing_strategy == RoutingStrategy.RANDOM:
            return self._select_random(available_instances)
        else:
            return available_instances[0]
    
    def _select_primary_first(self, available_instances: List[str]) -> str:
        """优先选择主实例 - 简化版本，始终选择主实例"""
        # 查找instance_1开头的实例
        primary_instances = [inst for inst in available_instances if 'instance_1' in inst]
        
        if primary_instances:
            # 始终使用主实例，不考虑负载
            primary_instance = primary_instances[0]
            self.logger.info(f"使用主实例: {primary_instance}")
            return primary_instance
        
        # 如果没有主实例，则使用第一个可用实例
        self.logger.warning(f"未找到主实例，使用第一个可用实例: {available_instances[0]}")
        return available_instances[0]
    
    def _select_least_loaded(self, available_instances: List[str]) -> str:
        """选择负载最轻的实例"""
        best_instance = available_instances[0]
        best_load = float('inf')
        
        for instance_id in available_instances:
            status = self.instance_manager.get_instance_status(instance_id)
            if status:
                load = status['active_requests'] / status['max_concurrent_requests']
                if load < best_load:
                    best_load = load
                    best_instance = instance_id
        
        return best_instance
    
    def _select_round_robin(self, available_instances: List[str]) -> str:
        """轮询选择实例"""
        instance = available_instances[self.round_robin_counter % len(available_instances)]
        self.round_robin_counter += 1
        return instance
    
    def _select_random(self, available_instances: List[str]) -> str:
        """随机选择实例"""
        import random
        return random.choice(available_instances)
    
    async def _acquire_instance_lock(self, instance_id: str) -> bool:
        """获取实例锁"""
        try:
            # 增加活跃请求计数
            if instance_id in self.instance_manager.runtime_states:
                runtime = self.instance_manager.runtime_states[instance_id]
                config = self.instance_manager.instances[instance_id]
                
                if runtime.active_requests < config.max_concurrent_requests:
                    runtime.active_requests += 1
                    runtime.last_activity = time.time()
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"获取实例锁失败: {e}")
            return False
    
    async def _release_instance_lock(self, instance_id: str):
        """释放实例锁"""
        try:
            if instance_id in self.instance_manager.runtime_states:
                runtime = self.instance_manager.runtime_states[instance_id]
                if runtime.active_requests > 0:
                    runtime.active_requests -= 1
                    
        except Exception as e:
            self.logger.error(f"释放实例锁失败: {e}")
    
    async def _process_request_on_instance(self, context: RequestContext) -> Any:
        """在指定实例上处理请求"""
        instance_id = context.instance_id
        request = context.original_request
        
        if not instance_id or instance_id not in self.instance_manager.runtime_states:
            raise HTTPException(status_code=500, detail="实例不可用")
        
        runtime = self.instance_manager.runtime_states[instance_id]
        if not runtime.page:
            raise HTTPException(status_code=500, detail="实例页面不可用")
        
        try:
            self.logger.info(f"[{context.request_id}] 在实例 {instance_id} 上处理请求")
            
            # 这里需要调用实际的页面操作逻辑
            # 将ChatCompletionRequest转换为页面操作
            response = await self._execute_chat_completion_on_page(
                runtime.page, 
                request, 
                context.request_id
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"[{context.request_id}] 在实例 {instance_id} 上处理请求失败: {e}")
            
            # 如果启用故障转移，尝试其他实例
            if self.enable_failover and context.retry_count < context.max_retries:
                context.retry_count += 1
                self.logger.info(f"[{context.request_id}] 尝试故障转移，重试次数: {context.retry_count}")
                
                # 释放当前实例锁
                await self._release_instance_lock(instance_id)
                
                # 选择新实例
                new_instance_id = await self._select_instance(context)
                if new_instance_id and new_instance_id != instance_id:
                    context.instance_id = new_instance_id
                    
                    if await self._acquire_instance_lock(new_instance_id):
                        return await self._process_request_on_instance(context)
            
            raise
    
    async def _execute_chat_completion_on_page(self, 
                                             page, 
                                             request: ChatCompletionRequest, 
                                             request_id: str) -> Any:
        """在页面上执行聊天完成请求"""
        try:
            # 导入页面操作函数
            from browser_utils.operations import (
                switch_ai_studio_model,
                get_response_via_copy_button,
                _wait_for_response_completion
            )
            from api_utils.processing import prepare_combined_prompt
            
            # 切换模型（如果需要）
            if request.model:
                try:
                    success = await switch_ai_studio_model(page, request.model, request_id)
                    if not success:
                        raise HTTPException(
                            status_code=400,
                            detail=f"[{request_id}] 未能切换到模型 '{request.model}'。请确保模型可用。"
                        )
                except Exception as e:
                    self.logger.error(f"[{request_id}] 模型切换失败: {e}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"[{request_id}] 未能切换到模型 '{request.model}'。请确保模型可用。"
                    )
            
            # 准备提示词
            combined_prompt = prepare_combined_prompt(request.messages)
            
            # 输入提示词
            await self._input_prompt_to_page(page, combined_prompt)
            
            # 等待响应完成
            await _wait_for_response_completion(page)
            
            # 获取响应内容
            response_content = await get_response_via_copy_button(page)
            
            # 构造响应
            if request.stream:
                return self._create_streaming_response(response_content, request_id)
            else:
                return self._create_non_streaming_response(response_content, request_id, request.model)
                
        except Exception as e:
            self.logger.error(f"[{request_id}] 页面操作失败: {e}")
            raise
    
    async def _input_prompt_to_page(self, page, prompt: str):
        """将提示词输入到页面"""
        try:
            # 查找输入框
            input_selector = 'textarea[placeholder*="输入"], textarea[placeholder*="Enter"], div[contenteditable="true"]'
            
            # 等待输入框出现
            await page.wait_for_selector(input_selector, timeout=10000)
            
            # 清空并输入内容
            await page.fill(input_selector, prompt)
            
            # 发送消息
            send_button = page.locator('button[aria-label*="发送"], button:has-text("发送"), button[data-testid="send-button"]')
            await send_button.click()
            
        except Exception as e:
            self.logger.error(f"输入提示词失败: {e}")
            raise
    
    def _create_streaming_response(self, content: str, request_id: str):
        """创建流式响应"""
        from api_utils.responses import generate_sse_chunk, generate_sse_stop_chunk
        
        async def generate():
            # 分块发送内容
            chunk_size = 50
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                yield generate_sse_chunk(chunk, request_id)
                await asyncio.sleep(0.01)  # 模拟流式延迟
            
            # 发送结束标记
            yield generate_sse_stop_chunk(request_id)
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    def _create_non_streaming_response(self, content: str, request_id: str, model: str):
        """创建非流式响应"""
        return {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": len(content.split()),
                "total_tokens": len(content.split())
            }
        }
    
    def _record_success(self, context: RequestContext):
        """记录成功请求"""
        response_time = time.time() - context.started_at
        
        self.stats['successful_requests'] += 1
        
        # 更新平均响应时间
        total_requests = self.stats['successful_requests'] + self.stats['failed_requests']
        if total_requests > 0:
            current_avg = self.stats['average_response_time']
            self.stats['average_response_time'] = (
                current_avg * (total_requests - 1) + response_time
            ) / total_requests
        
        self.logger.info(f"[{context.request_id}] 请求成功，响应时间: {response_time:.2f}s")
    
    def _record_failure(self, context: RequestContext):
        """记录失败请求"""
        self.stats['failed_requests'] += 1
        self.logger.warning(f"[{context.request_id}] 请求失败")
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取路由器健康状态"""
        available_instances = self.instance_manager.get_available_instances()
        total_instances = len(self.instance_manager.instances)
        
        # 计算成功率
        total_requests = self.stats['successful_requests'] + self.stats['failed_requests']
        success_rate = (self.stats['successful_requests'] / total_requests * 100) if total_requests > 0 else 0
        
        # 健康状态评估
        if len(available_instances) == 0:
            status = "critical"
        elif len(available_instances) < total_instances * 0.5:
            status = "warning"
        elif success_rate < 90:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            'status': status,
            'total_instances': total_instances,
            'available_instances': len(available_instances),
            'active_requests': len(self.active_requests),
            'success_rate': success_rate,
            'average_response_time': self.stats['average_response_time'],
            'total_requests': total_requests,
            'routing_errors': self.stats['routing_errors'],
            'timestamp': time.time()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        return {
            'global_stats': self.stats,
            'active_requests': len(self.active_requests),
            'request_history_size': len(self.request_history),
            'routing_strategy': self.routing_strategy.value,
            'enable_failover': self.enable_failover,
            'health_status': self.get_health_status()
        }