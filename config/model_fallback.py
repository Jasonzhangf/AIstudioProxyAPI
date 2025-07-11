#!/usr/bin/env python3
# model_fallback.py - 模型降级配置和管理

import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger("ModelFallback")

@dataclass
class ModelStatus:
    """模型状态"""
    available: bool = True
    quota_exceeded_time: Optional[float] = None
    error_count: int = 0
    last_error_message: str = ""

@dataclass 
class InstanceModelStatus:
    """实例级别的模型状态管理"""
    instance_id: str
    model_status: Dict[str, ModelStatus] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, init=False)
    
    def mark_model_quota_exceeded(self, model_id: str, error_message: str = "") -> None:
        """标记模型quota已达上限"""
        with self._lock:
            if model_id not in self.model_status:
                self.model_status[model_id] = ModelStatus()
            
            status = self.model_status[model_id]
            status.available = False
            status.quota_exceeded_time = time.time()
            status.error_count += 1
            status.last_error_message = error_message
            
            logger.warning(f"[实例{self.instance_id}] 模型 {model_id} 已达quota上限: {error_message}")
    
    def is_model_available(self, model_id: str) -> bool:
        """检查模型是否可用"""
        with self._lock:
            if model_id not in self.model_status:
                return True
                
            status = self.model_status[model_id]
            if not status.available and status.quota_exceeded_time:
                # 检查是否已过了冷却期（默认1小时）
                if time.time() - status.quota_exceeded_time > 3600:
                    logger.info(f"[实例{self.instance_id}] 模型 {model_id} quota冷却期已过，重新标记为可用")
                    status.available = True
                    status.quota_exceeded_time = None
                    return True
            
            return status.available
    
    def get_available_models(self, all_models: List[str]) -> List[str]:
        """获取当前可用的模型列表"""
        return [model for model in all_models if self.is_model_available(model)]

class ModelFallbackManager:
    """模型降级管理器"""
    
    # 模型降级优先级配置
    MODEL_FALLBACK_MAP = {
        "gemini-2.5-pro-preview-03-25": [
            "gemini-2.0-flash-latest",
            "gemini-1.5-pro-latest", 
            "gemini-1.5-flash-latest"
        ],
        "gemini-2.5-flash-preview": [
            "gemini-2.0-flash-latest",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest"
        ],
        "gemini-2.0-flash-latest": [
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest"
        ],
        "gemini-1.5-pro-latest": [
            "gemini-1.5-flash-latest",
            "gemini-2.0-flash-latest"
        ]
    }
    
    def __init__(self):
        self.instance_statuses: Dict[str, InstanceModelStatus] = {}
        self._lock = Lock()
    
    def get_or_create_instance_status(self, instance_id: str) -> InstanceModelStatus:
        """获取或创建实例状态"""
        with self._lock:
            if instance_id not in self.instance_statuses:
                self.instance_statuses[instance_id] = InstanceModelStatus(instance_id)
            return self.instance_statuses[instance_id]
    
    def mark_model_quota_exceeded(self, instance_id: str, model_id: str, error_message: str = "") -> None:
        """标记某个实例的模型quota已达上限"""
        instance_status = self.get_or_create_instance_status(instance_id)
        instance_status.mark_model_quota_exceeded(model_id, error_message)
    
    def get_fallback_model(self, instance_id: str, original_model: str) -> Optional[str]:
        """获取降级模型
        
        Args:
            instance_id: 实例ID
            original_model: 原始请求的模型
            
        Returns:
            可用的降级模型ID，如果没有则返回None
        """
        instance_status = self.get_or_create_instance_status(instance_id)
        
        # 检查原始模型是否还可用
        if instance_status.is_model_available(original_model):
            return original_model
        
        # 查找降级模型
        fallback_models = self.MODEL_FALLBACK_MAP.get(original_model, [])
        
        for fallback_model in fallback_models:
            if instance_status.is_model_available(fallback_model):
                logger.info(f"[实例{instance_id}] 模型 {original_model} 不可用，自动降级为 {fallback_model}")
                return fallback_model
        
        logger.warning(f"[实例{instance_id}] 模型 {original_model} 及其所有降级选项都不可用")
        return None
    
    def get_best_available_instance(self, model_id: str) -> Optional[str]:
        """获取最适合处理指定模型的实例
        
        Args:
            model_id: 要处理的模型ID
            
        Returns:
            最适合的实例ID，如果所有实例都不可用则返回None
        """
        with self._lock:
            available_instances = []
            
            for instance_id, instance_status in self.instance_statuses.items():
                if instance_status.is_model_available(model_id):
                    available_instances.append(instance_id)
            
            if available_instances:
                # 简单策略：返回第一个可用的实例
                # 可以在此处添加更复杂的负载均衡逻辑
                selected_instance = available_instances[0]
                logger.info(f"为模型 {model_id} 选择实例 {selected_instance}")
                return selected_instance
            
            logger.warning(f"没有实例可以处理模型 {model_id}")
            return None
    
    def get_status_summary(self) -> Dict:
        """获取所有实例和模型的状态摘要"""
        with self._lock:
            summary = {}
            for instance_id, instance_status in self.instance_statuses.items():
                instance_summary = {}
                with instance_status._lock:
                    for model_id, status in instance_status.model_status.items():
                        instance_summary[model_id] = {
                            "available": status.available,
                            "error_count": status.error_count,
                            "last_error": status.last_error_message,
                            "quota_exceeded_time": status.quota_exceeded_time
                        }
                summary[instance_id] = instance_summary
            return summary

# 全局实例
model_fallback_manager = ModelFallbackManager()