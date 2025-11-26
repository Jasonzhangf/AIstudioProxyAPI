#!/usr/bin/env python3
"""
多账号路由层
提供统一 API 入口，将请求分发到多个后端实例
"""

import os
import sys
import json
import time
import hashlib
import asyncio
import logging
import logging.handlers
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import aiohttp
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn


@dataclass
class BackendInstance:
    """后端实例信息"""
    id: str
    port: int
    weight: int
    enabled: bool
    max_concurrent: int
    current_concurrent: int = 0
    status: str = "unknown"  # unknown, healthy, unhealthy
    last_heartbeat: Optional[float] = None
    total_requests: int = 0
    failed_requests: int = 0


class RouterStrategy:
    """路由策略基类"""
    
    def __init__(self, instances: List[BackendInstance]):
        self.instances = instances
    
    def get_instance(self, request: Request = None) -> Optional[BackendInstance]:
        """获取后端实例"""
        raise NotImplementedError


class RoundRobinStrategy(RouterStrategy):
    """轮询策略"""
    
    def __init__(self, instances: List[BackendInstance]):
        super().__init__(instances)
        self._current_index = 0
    
    def get_instance(self, request: Request = None) -> Optional[BackendInstance]:
        """轮询获取实例"""
        # 过滤健康且未达并发上限的实例
        available = [
            inst for inst in self.instances
            if inst.enabled and inst.status == "healthy" 
            and inst.current_concurrent < inst.max_concurrent
        ]
        
        if not available:
            return None
        
        # 轮询选择
        instance = available[self._current_index % len(available)]
        self._current_index += 1
        return instance


class WeightedStrategy(RouterStrategy):
    """权重策略"""
    
    def get_instance(self, request: Request = None) -> Optional[BackendInstance]:
        """按权重选择实例"""
        available = [
            inst for inst in self.instances
            if inst.enabled and inst.status == "healthy"
            and inst.current_concurrent < inst.max_concurrent
        ]
        
        if not available:
            return None
        
        # 计算总权重
        total_weight = sum(inst.weight for inst in available)
        
        # 随机选择
        import random
        r = random.randint(1, total_weight)
        
        current = 0
        for inst in available:
            current += inst.weight
            if r <= current:
                return inst
        
        return available[-1]


class HashStrategy(RouterStrategy):
    """哈希策略（基于 API Key）"""
    
    def get_instance(self, request: Request = None) -> Optional[BackendInstance]:
        """按 API Key 哈希选择实例"""
        available = [
            inst for inst in self.instances
            if inst.enabled and inst.status == "healthy"
            and inst.current_concurrent < inst.max_concurrent
        ]
        
        if not available:
            return None
        
        if not request:
            # 无请求时使用轮询
            return RoundRobinStrategy(available).get_instance()
        
        # 获取 API Key
        api_key = self._get_api_key(request)
        if not api_key:
            return RoundRobinStrategy(available).get_instance()
        
        # 哈希计算
        hash_value = int(hashlib.md5(api_key.encode()).hexdigest(), 16)
        index = hash_value % len(available)
        
        return available[index]
    
    def _get_api_key(self, request: Request) -> Optional[str]:
        """从请求中提取 API Key"""
        # 从 Authorization 头
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # 从 X-API-Key 头
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        return None


class MultiAccountRouter:
    """多账号路由器"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self.instances: Dict[str, BackendInstance] = {}
        self.strategy: Optional[RouterStrategy] = None
        self.logger = self._setup_logging()
        self.app = FastAPI(title="Multi-Account Router")
        self._setup_routes()
        
        # 初始化实例
        self._initialize_instances()
        
        # 设置路由策略
        self._setup_strategy()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("MultiAccountRouter")
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        
        logger.addHandler(handler)
        return logger
    
    def _initialize_instances(self):
        """初始化后端实例"""
        accounts = self.config.get("accounts", [])
        
        for account in accounts:
            instance = BackendInstance(
                id=account["id"],
                port=account["port"],
                weight=account.get("weight", 1),
                enabled=account.get("enabled", True),
                max_concurrent=account.get("max_concurrent", 3)
            )
            self.instances[instance.id] = instance
            self.logger.info(f"初始化后端实例: {instance.id} (端口: {instance.port})")
    
    def _setup_strategy(self):
        """设置路由策略"""
        strategy_type = self.config.get("router", {}).get("strategy", "roundrobin")
        instances = list(self.instances.values())
        
        if strategy_type == "roundrobin":
            self.strategy = RoundRobinStrategy(instances)
        elif strategy_type == "weighted":
            self.strategy = WeightedStrategy(instances)
        elif strategy_type == "hash":
            self.strategy = HashStrategy(instances)
        else:
            self.logger.warning(f"未知的路由策略 '{strategy_type}'，使用轮询")
            self.strategy = RoundRobinStrategy(instances)
        
        self.logger.info(f"路由策略已设置: {strategy_type}")
    
    def _setup_routes(self):
        """设置 API 路由"""
        
        @self.app.get("/")
        async def root():
            return {"message": "Multi-Account Router", "version": "1.0.0"}
        
        @self.app.get("/health")
        async def health_check():
            """健康检查"""
            healthy_count = sum(1 for inst in self.instances.values() if inst.status == "healthy")
            total_count = len(self.instances)
            
            return {
                "status": "healthy" if healthy_count > 0 else "unhealthy",
                "instances": {
                    "total": total_count,
                    "healthy": healthy_count,
                    "unhealthy": total_count - healthy_count
                }
            }
        
        @self.app.get("/v1/models")
        async def list_models():
            """获取模型列表（从第一个健康实例）"""
            healthy_instances = [
                inst for inst in self.instances.values()
                if inst.enabled and inst.status == "healthy"
            ]
            
            if not healthy_instances:
                raise HTTPException(503, "No healthy instances available")
            
            # 从第一个健康实例获取
            instance = healthy_instances[0]
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://127.0.0.1:{instance.port}/v1/models") as resp:
                        if resp.status == 200:
                            return await resp.json()
                        else:
                            raise HTTPException(resp.status, await resp.text())
            except Exception as e:
                self.logger.error(f"获取模型列表失败: {e}")
                raise HTTPException(500, str(e))
        
        @self.app.post("/v1/chat/completions")
        async def chat_completions(request: Request):
            """聊天完成（路由到后端实例）"""
            
            # 获取请求体
            body = await request.body()
            
            # 选择后端实例
            instance = self.strategy.get_instance(request)
            if not instance:
                raise HTTPException(503, "No available instances (all unhealthy or at capacity)")
            
            # 增加并发计数
            instance.current_concurrent += 1
            instance.total_requests += 1
            
            try:
                # 转发请求
                async with aiohttp.ClientSession() as session:
                    # 复制请求头
                    headers = {}
                    for key, value in request.headers.items():
                        if key.lower() not in ['host', 'content-length']:
                            headers[key] = value
                    
                    # 发送请求
                    async with session.post(
                        f"http://127.0.0.1:{instance.port}/v1/chat/completions",
                        data=body,
                        headers=headers
                    ) as resp:
                        
                        # 检查是否是流式响应
                        is_stream = resp.headers.get('content-type', '').startswith('text/event-stream')
                        
                        if is_stream:
                            # 流式响应
                            async def stream_generator():
                                try:
                                    async for line in resp.content:
                                        if line:
                                            yield line
                                finally:
                                    # 减少并发计数
                                    instance.current_concurrent -= 1
                            
                            return StreamingResponse(
                                stream_generator(),
                                status_code=resp.status,
                                headers=dict(resp.headers)
                            )
                        else:
                            # 非流式响应
                            response_data = await resp.json()
                            instance.current_concurrent -= 1
                            return JSONResponse(
                                content=response_data,
                                status_code=resp.status,
                                headers=dict(resp.headers)
                            )
            
            except Exception as e:
                instance.current_concurrent -= 1
                instance.failed_requests += 1
                self.logger.error(f"请求转发失败 (实例 {instance.id}): {e}")
                raise HTTPException(500, f"Backend error: {str(e)}")
        
        @self.app.get("/router/status")
        async def router_status():
            """路由器状态"""
            instances_status = []
            
            for inst in self.instances.values():
                instances_status.append({
                    "id": inst.id,
                    "port": inst.port,
                    "weight": inst.weight,
                    "enabled": inst.enabled,
                    "status": inst.status,
                    "current_concurrent": inst.current_concurrent,
                    "max_concurrent": inst.max_concurrent,
                    "total_requests": inst.total_requests,
                    "failed_requests": inst.failed_requests,
                    "last_heartbeat": inst.last_heartbeat
                })
            
            return {
                "strategy": self.config.get("router", {}).get("strategy", "roundrobin"),
                "instances": instances_status
            }
        
        @self.app.post("/router/health-check")
        async def trigger_health_check():
            """触发健康检查"""
            await self._perform_health_check()
            return {"status": "completed"}
    
    async def _perform_health_check(self):
        """执行健康检查"""
        self.logger.info("执行健康检查...")
        
        for instance_id, instance in self.instances.items():
            if not instance.enabled:
                continue
            
            try:
                # 检查端口是否响应
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://127.0.0.1:{instance.port}/health",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            instance.status = "healthy"
                            instance.last_heartbeat = time.time()
                        else:
                            instance.status = "unhealthy"
            except Exception as e:
                instance.status = "unhealthy"
                self.logger.warning(f"健康检查失败 (实例 {instance_id}): {e}")
    
    def start_health_check_loop(self):
        """启动健康检查循环"""
        async def health_check_task():
            interval = self.config.get("router", {}).get("health_check_interval", 30)
            while True:
                await self._perform_health_check()
                await asyncio.sleep(interval)
        
        asyncio.create_task(health_check_task())
        self.logger.info("健康检查循环已启动")


def main():
    """主函数"""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "multi_account_config.json"
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)
    
    # 启动路由器
    router = MultiAccountRouter(config_path)
    
    # 启动健康检查
    router.start_health_check_loop()
    
    # 启动 FastAPI
    router_config = router.config.get("router", {})
    host = router_config.get("host", "0.0.0.0")
    port = router_config.get("port", 8080)
    
    router.logger.info(f"启动路由器，监听 {host}:{port}")
    uvicorn.run(router.app, host=host, port=port)


if __name__ == "__main__":
    main()
