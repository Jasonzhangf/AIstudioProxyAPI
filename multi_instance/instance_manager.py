"""
多实例管理器模块
负责管理多个AI Studio实例的生命周期、路由和状态
"""
import asyncio
import json
import os
import time
import uuid
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
from playwright.async_api import Page as AsyncPage, Browser as AsyncBrowser

class InstanceStatus(Enum):
    """实例状态枚举"""
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    DISABLED = "disabled"
    STOPPED = "stopped"

@dataclass
class InstanceConfig:
    """实例配置"""
    instance_id: str
    auth_profile_path: str
    email: str
    enabled: bool = True
    port: int = 9222
    model_whitelist: Set[str] = field(default_factory=set)
    model_blacklist: Set[str] = field(default_factory=set)
    max_concurrent_requests: int = 1
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)

@dataclass
class InstanceState:
    """实例运行状态"""
    instance_id: str
    status: InstanceStatus
    config: InstanceConfig
    page: Optional[AsyncPage] = None
    browser: Optional[AsyncBrowser] = None
    lock: Optional[asyncio.Lock] = None
    current_model_id: Optional[str] = None
    available_models: List[Dict[str, Any]] = field(default_factory=list)
    active_requests: int = 0
    total_requests: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    started_at: Optional[float] = None
    last_heartbeat: float = field(default_factory=time.time)

class MultiInstanceManager:
    """多实例管理器"""
    
    def __init__(self, 
                 auth_profiles_dir: str = "auth_profiles",
                 config_dir: str = "multi_instance/config",
                 logger: Optional[logging.Logger] = None):
        self.auth_profiles_dir = Path(auth_profiles_dir)
        self.config_dir = Path(config_dir)
        self.logger = logger or logging.getLogger(__name__)
        
        # 实例状态管理
        self.instances: Dict[str, InstanceState] = {}
        self.instance_configs: Dict[str, InstanceConfig] = {}
        
        # 全局管理锁
        self.manager_lock = asyncio.Lock()
        
        # 路由权重配置
        self.routing_weights: Dict[str, float] = {}
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self._load_instance_configs()
    
    def _load_instance_configs(self):
        """加载实例配置"""
        try:
            config_file = self.config_dir / "instances.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for instance_data in data.get('instances', []):
                    # 创建配置实例，处理可能缺失的字段
                    config = InstanceConfig(
                        instance_id=instance_data.get('instance_id', ''),
                        auth_profile_path=instance_data.get('auth_profile_path', ''),
                        email=instance_data.get('email', ''),
                        enabled=instance_data.get('enabled', True),
                        port=instance_data.get('port', 9222),
                        max_concurrent_requests=instance_data.get('max_concurrent_requests', 1),
                        created_at=instance_data.get('created_at', time.time()),
                        last_used_at=instance_data.get('last_used_at', time.time())
                    )
                    # 将集合类型正确转换
                    config.model_whitelist = set(instance_data.get('model_whitelist', []))
                    config.model_blacklist = set(instance_data.get('model_blacklist', []))
                    self.instance_configs[config.instance_id] = config
                    
                self.routing_weights = data.get('routing_weights', {})
                    
            self.logger.info(f"已加载 {len(self.instance_configs)} 个实例配置")
        except Exception as e:
            self.logger.error(f"加载实例配置失败: {e}")
            # 如果加载失败，使用默认配置
            self._create_default_configs()
    
    def _create_default_configs(self):
        """创建默认配置"""
        # 如果没有配置文件，尝试从认证文件创建默认配置
        profiles = self.discover_auth_profiles()
        for profile in profiles:
            email = profile['email']
            auth_file = profile['auth_file']
            instance_id = f"instance_{email.replace('@', '_at_').replace('.', '_')}"
            
            config = InstanceConfig(
                instance_id=instance_id,
                auth_profile_path=auth_file,
                email=email,
                port=9222 + len(self.instance_configs),
                enabled=True
            )
            
            self.instance_configs[instance_id] = config
        
        if self.instance_configs:
            self._save_instance_configs()
            self.logger.info(f"创建了 {len(self.instance_configs)} 个默认实例配置")
    
    def _save_instance_configs(self):
        """保存实例配置"""
        try:
            # 确保配置目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            config_file = self.config_dir / "instances.json"
            data = {
                'instances': [],
                'routing_weights': self.routing_weights,
                'version': '1.0',
                'last_updated': time.time()
            }
            
            for config in self.instance_configs.values():
                instance_data = {
                    'instance_id': config.instance_id,
                    'auth_profile_path': config.auth_profile_path,
                    'email': config.email,
                    'enabled': config.enabled,
                    'port': config.port,
                    'model_whitelist': list(config.model_whitelist),
                    'model_blacklist': list(config.model_blacklist),
                    'max_concurrent_requests': config.max_concurrent_requests,
                    'created_at': config.created_at,
                    'last_used_at': config.last_used_at
                }
                data['instances'].append(instance_data)
                
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"已保存 {len(self.instance_configs)} 个实例配置到 {config_file}")
        except Exception as e:
            self.logger.error(f"保存实例配置失败: {e}")
            raise  # 重新抛出异常，让调用者知道保存失败
    
    def discover_auth_profiles(self) -> List[Dict[str, str]]:
        """发现可用的认证配置文件 - 只从multi文件夹读取"""
        profiles = []
        
        # 只搜索 multi 目录
        profile_dir = self.auth_profiles_dir / 'multi'
        if profile_dir.exists():
            for auth_file in profile_dir.glob("*.json"):
                try:
                    # 从文件名推断邮箱
                    email = auth_file.stem
                    if email.startswith("auth_state_"):
                        continue  # 跳过临时文件
                        
                    profiles.append({
                        'email': email,
                        'auth_file': str(auth_file),
                        'directory': 'multi'
                    })
                except Exception as e:
                    self.logger.warning(f"处理认证文件 {auth_file} 时出错: {e}")
        
        return profiles
    
    def auto_create_instances(self) -> List[str]:
        """基于auth_profiles自动创建实例配置"""
        profiles = self.discover_auth_profiles()
        new_instances = []
        
        for profile in profiles:
            email = profile['email']
            auth_file = profile['auth_file']
            
            # 检查是否已存在配置
            existing_instance = None
            for config in self.instance_configs.values():
                if config.email == email:
                    existing_instance = config
                    break
            
            if existing_instance:
                # 更新现有配置的认证文件路径
                existing_instance.auth_profile_path = auth_file
                self.logger.info(f"更新实例 {existing_instance.instance_id} 的认证文件路径")
            else:
                # 创建新实例配置
                instance_id = f"instance_{len(self.instance_configs) + 1}_{email.replace('@', '_at_').replace('.', '_')}"
                
                config = InstanceConfig(
                    instance_id=instance_id,
                    auth_profile_path=auth_file,
                    email=email,
                    port=9222 + len(self.instance_configs),
                    enabled=True
                )
                
                self.instance_configs[instance_id] = config
                new_instances.append(instance_id)
                self.logger.info(f"创建新实例配置: {instance_id} ({email})")
        
        if new_instances:
            self._save_instance_configs()
        
        return new_instances
    
    async def start_instance(self, instance_id: str, 
                           browser: AsyncBrowser, 
                           page: AsyncPage,
                           partial: bool = False) -> bool:
        """启动指定实例"""
        if instance_id not in self.instance_configs:
            self.logger.error(f"实例配置不存在: {instance_id}")
            return False
        
        config = self.instance_configs[instance_id]
        
        if not config.enabled:
            self.logger.warning(f"实例被禁用: {instance_id}")
            return False
        
        async with self.manager_lock:
            # 创建实例状态
            if partial:
                # 部分状态实例（等待登录）
                instance_state = InstanceState(
                    instance_id=instance_id,
                    status=InstanceStatus.STARTING,  # 保持启动中状态
                    config=config,
                    page=page,
                    browser=browser,
                    lock=asyncio.Lock(),
                    started_at=time.time()
                )
                self.instances[instance_id] = instance_state
                self.logger.info(f"实例 {instance_id} 保存为部分状态（等待登录）")
                return True
            else:
                # 正常启动流程
                instance_state = InstanceState(
                    instance_id=instance_id,
                    status=InstanceStatus.STARTING,
                    config=config,
                    page=page,
                    browser=browser,
                    lock=asyncio.Lock(),
                    started_at=time.time()
                )
                
                self.instances[instance_id] = instance_state
                self.logger.info(f"正在启动实例: {instance_id}")
                
                try:
                    # 初始化页面完成后的处理
                    # 加载模型状态和处理认证
                    await self._post_page_initialization(instance_state)
                    
                    instance_state.status = InstanceStatus.READY
                    self.logger.info(f"实例启动成功: {instance_id}")
                    return True
                    
                except Exception as e:
                    instance_state.status = InstanceStatus.ERROR
                    instance_state.last_error = str(e)
                    self.logger.error(f"实例启动失败: {instance_id}, 错误: {e}")
                    return False
    
    async def upgrade_partial_instance(self, instance_id: str) -> bool:
        """将部分状态实例升级为完全就绪状态"""
        if instance_id not in self.instances:
            self.logger.warning(f"实例不存在: {instance_id}")
            return False
        
        instance_state = self.instances[instance_id]
        
        if instance_state.status != InstanceStatus.STARTING:
            self.logger.warning(f"实例 {instance_id} 状态不是STARTING，无法升级")
            return False
        
        try:
            self.logger.info(f"开始升级部分状态实例: {instance_id}")
            
            # 执行完整的页面初始化后处理
            await self._post_page_initialization(instance_state)
            
            instance_state.status = InstanceStatus.READY
            self.logger.info(f"实例 {instance_id} 成功升级为完全就绪状态")
            return True
            
        except Exception as e:
            instance_state.status = InstanceStatus.ERROR
            instance_state.last_error = str(e)
            self.logger.error(f"实例 {instance_id} 升级失败: {e}")
            return False
    
    async def stop_instance(self, instance_id: str) -> bool:
        """停止指定实例"""
        if instance_id not in self.instances:
            self.logger.warning(f"实例不存在: {instance_id}")
            return False
        
        async with self.manager_lock:
            instance_state = self.instances[instance_id]
            
            try:
                # 等待当前请求完成
                if instance_state.lock:
                    async with instance_state.lock:
                        instance_state.status = InstanceStatus.STOPPED
                        
                        # 清理资源
                        if instance_state.page:
                            await instance_state.page.close()
                        if instance_state.browser:
                            await instance_state.browser.close()
                        
                        del self.instances[instance_id]
                        self.logger.info(f"实例已停止: {instance_id}")
                        return True
                        
            except Exception as e:
                self.logger.error(f"停止实例失败: {instance_id}, 错误: {e}")
                return False
    
    def get_available_instances(self, exclude_instance: Optional[str] = None) -> List[str]:
        """获取可用的实例ID列表
        
        Args:
            exclude_instance: 要排除的实例ID
        """
        available = []
        for instance_id, state in self.instances.items():
            # 跳过被排除的实例
            if exclude_instance and instance_id == exclude_instance:
                continue
            
            # 检查实例是否可用
            if (state.status == InstanceStatus.READY and 
                state.active_requests < state.config.max_concurrent_requests):
                available.append(instance_id)
        return available
    
    def select_instance_for_request(self, model_id: Optional[str] = None, 
                                  exclude_instance: Optional[str] = None,
                                  strategy: str = "load_balance") -> Optional[str]:
        """为请求选择最佳实例
        
        Args:
            model_id: 模型ID，用于过滤支持该模型的实例
            exclude_instance: 要排除的实例ID
            strategy: 选择策略 ("load_balance", "round_robin", "least_response_time")
        """
        available_instances = self.get_available_instances(exclude_instance)
        
        if not available_instances:
            return None
        
        # 过滤支持请求模型的实例
        if model_id:
            filtered_instances = []
            for instance_id in available_instances:
                state = self.instances[instance_id]
                config = state.config
                
                # 检查黑名单
                if model_id in config.model_blacklist:
                    continue
                
                # 检查白名单（如果设置了白名单）
                if config.model_whitelist and model_id not in config.model_whitelist:
                    continue
                
                filtered_instances.append(instance_id)
            
            available_instances = filtered_instances
        
        if not available_instances:
            return None
        
        # 根据策略选择实例
        if strategy == "round_robin":
            return self._select_instance_round_robin(available_instances)
        elif strategy == "least_response_time":
            return self._select_instance_least_response_time(available_instances)
        else:  # load_balance
            return self._select_instance_load_balance(available_instances)
    
    def _select_instance_load_balance(self, available_instances: List[str]) -> Optional[str]:
        """基于负载选择实例"""
        best_instance = None
        best_score = float('inf')
        
        for instance_id in available_instances:
            state = self.instances[instance_id]
            
            # 计算负载分数（越低越好）
            load_score = state.active_requests / state.config.max_concurrent_requests
            
            # 考虑路由权重
            weight = self.routing_weights.get(instance_id, 1.0)
            final_score = load_score / weight
            
            if final_score < best_score:
                best_score = final_score
                best_instance = instance_id
        
        return best_instance
    
    def _select_instance_round_robin(self, available_instances: List[str]) -> Optional[str]:
        """轮询选择实例"""
        if not available_instances:
            return None
        
        # 简单的轮询实现：选择第一个实例
        # 在实际应用中，可以维护一个计数器来实现真正的轮询
        return available_instances[0]
    
    def _select_instance_least_response_time(self, available_instances: List[str]) -> Optional[str]:
        """基于最少响应时间选择实例（简化实现）"""
        # 在这个简化实现中，我们使用活跃请求数作为响应时间的近似值
        best_instance = None
        min_requests = float('inf')
        
        for instance_id in available_instances:
            state = self.instances[instance_id]
            if state.active_requests < min_requests:
                min_requests = state.active_requests
                best_instance = instance_id
        
        return best_instance
    
    async def acquire_instance_lock(self, instance_id: str) -> bool:
        """获取实例锁"""
        if instance_id not in self.instances:
            return False
        
        state = self.instances[instance_id]
        
        if state.status != InstanceStatus.READY:
            return False
        
        # 检查并发限制
        if state.active_requests >= state.config.max_concurrent_requests:
            return False
        
        try:
            await state.lock.acquire()
            state.active_requests += 1
            state.total_requests += 1
            state.status = InstanceStatus.BUSY
            state.last_heartbeat = time.time()
            self.logger.debug(f"获取实例锁: {instance_id}")
            return True
        except Exception as e:
            self.logger.error(f"获取实例锁失败: {instance_id}, 错误: {e}")
            return False
    
    async def release_instance_lock(self, instance_id: str):
        """释放实例锁"""
        if instance_id not in self.instances:
            return
        
        state = self.instances[instance_id]
        
        try:
            state.active_requests = max(0, state.active_requests - 1)
            state.config.last_used_at = time.time()
            state.last_heartbeat = time.time()
            
            if state.active_requests == 0:
                state.status = InstanceStatus.READY
            
            if state.lock.locked():
                state.lock.release()
                
            self.logger.debug(f"释放实例锁: {instance_id}")
        except Exception as e:
            self.logger.error(f"释放实例锁失败: {instance_id}, 错误: {e}")
    
    def get_instance_state(self, instance_id: str) -> Optional[InstanceState]:
        """获取实例状态"""
        return self.instances.get(instance_id)
    
    def get_all_instances_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有实例状态"""
        status = {}
        
        for instance_id, state in self.instances.items():
            status[instance_id] = {
                'status': state.status.value,
                'email': state.config.email,
                'enabled': state.config.enabled,
                'port': state.config.port,
                'active_requests': state.active_requests,
                'total_requests': state.total_requests,
                'error_count': state.error_count,
                'last_error': state.last_error,
                'started_at': state.started_at,
                'last_heartbeat': state.last_heartbeat,
                'current_model_id': state.current_model_id,
                'available_models_count': len(state.available_models),
                'model_whitelist': list(state.config.model_whitelist),
                'model_blacklist': list(state.config.model_blacklist)
            }
        
        return status
    
    def update_instance_config(self, instance_id: str, **kwargs) -> bool:
        """更新实例配置"""
        if instance_id not in self.instance_configs:
            self.logger.warning(f"实例配置不存在: {instance_id}")
            return False
        
        config = self.instance_configs[instance_id]
        
        # 更新允许的配置项
        allowed_fields = ['enabled', 'model_whitelist', 'model_blacklist', 'max_concurrent_requests']
        
        updated_fields = []
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field in ['model_whitelist', 'model_blacklist']:
                    setattr(config, field, set(value) if isinstance(value, list) else value)
                else:
                    setattr(config, field, value)
                updated_fields.append(field)
        
        if updated_fields:
            self.logger.info(f"更新实例 {instance_id} 配置: {', '.join(updated_fields)}")
            self._save_instance_configs()
        
        # 如果实例正在运行，更新运行时状态
        if instance_id in self.instances:
            self.instances[instance_id].config = config
            self.logger.debug(f"更新实例 {instance_id} 运行时配置")
        
        return True
    
    def set_routing_weight(self, instance_id: str, weight: float):
        """设置实例路由权重"""
        if instance_id not in self.instance_configs:
            self.logger.warning(f"实例配置不存在: {instance_id}")
            return False
        
        # 验证权重值
        if weight <= 0:
            self.logger.warning(f"路由权重必须大于0: {weight}")
            return False
        
        old_weight = self.routing_weights.get(instance_id, 1.0)
        self.routing_weights[instance_id] = weight
        self._save_instance_configs()
        self.logger.info(f"更新实例 {instance_id} 路由权重: {old_weight} -> {weight}")
        return True
    
    def get_routing_weight(self, instance_id: str) -> float:
        """获取实例路由权重"""
        return self.routing_weights.get(instance_id, 1.0)
    
    def list_routing_weights(self) -> Dict[str, float]:
        """列出所有实例的路由权重"""
        return self.routing_weights.copy()
    
    def reset_routing_weight(self, instance_id: str):
        """重置实例路由权重为默认值"""
        if instance_id in self.routing_weights:
            old_weight = self.routing_weights[instance_id]
            del self.routing_weights[instance_id]
            self._save_instance_configs()
            self.logger.info(f"重置实例 {instance_id} 路由权重: {old_weight} -> 1.0")
    
    def set_default_routing_weights(self, weights: Dict[str, float]):
        """设置默认路由权重"""
        for instance_id, weight in weights.items():
            if weight > 0:  # 只设置有效的权重
                self.routing_weights[instance_id] = weight
        self._save_instance_configs()
        self.logger.info(f"设置默认路由权重: {weights}")
    
    async def _post_page_initialization(self, instance_state: InstanceState):
        """页面初始化完成后的处理"""
        try:
            if not instance_state.page:
                return
            
            # 导入模型处理函数
            from browser_utils.model_management import _handle_initial_model_state_and_storage
            
            # 处理初始模型状态
            await _handle_initial_model_state_and_storage(instance_state.page)
            
            self.logger.info(f"实例 {instance_state.instance_id} 页面初始化后处理完成")
            
        except Exception as e:
            self.logger.error(f"实例 {instance_state.instance_id} 页面初始化后处理失败: {e}")
            # 不抛出异常，允许实例继续启动
    
    def health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        health_status = {
            'timestamp': time.time(),
            'total_instances': len(self.instance_configs),
            'healthy_instances': 0,
            'unhealthy_instances': 0,
            'instance_health': {}
        }
        
        for instance_id, state in self.instances.items():
            instance_healthy = self._is_instance_healthy(state)
            if instance_healthy:
                health_status['healthy_instances'] += 1
            else:
                health_status['unhealthy_instances'] += 1
            
            health_status['instance_health'][instance_id] = {
                'healthy': instance_healthy,
                'status': state.status.value,
                'error_count': state.error_count,
                'last_error': state.last_error,
                'last_heartbeat': state.last_heartbeat
            }
        
        return health_status
    
    def _is_instance_healthy(self, state: InstanceState) -> bool:
        """检查单个实例是否健康"""
        # 实例状态为ERROR或DISABLED则不健康
        if state.status in [InstanceStatus.ERROR, InstanceStatus.DISABLED]:
            return False
        
        # 错误次数过多则不健康
        if state.error_count > 5:  # 可配置阈值
            return False
        
        # 超过30秒没有心跳则不健康
        if time.time() - state.last_heartbeat > 30:
            return False
        
        return True
    
    async def periodic_health_check(self, interval: int = 30):
        """定期健康检查"""
        while True:
            try:
                health_status = self.health_check()
                unhealthy_count = health_status['unhealthy_instances']
                
                if unhealthy_count > 0:
                    self.logger.warning(f"发现 {unhealthy_count} 个不健康的实例")
                    # 可以在这里添加自动恢复逻辑
                
                self.logger.debug(f"健康检查完成: {health_status['healthy_instances']} 健康, {unhealthy_count} 不健康")
                
                # 等待下次检查
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"定期健康检查失败: {e}")
                await asyncio.sleep(interval)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_instances = len(self.instance_configs)
        running_instances = len([s for s in self.instances.values() if s.status == InstanceStatus.READY])
        disabled_instances = len([c for c in self.instance_configs.values() if not c.enabled])
        error_instances = len([s for s in self.instances.values() if s.status == InstanceStatus.ERROR])
        busy_instances = len([s for s in self.instances.values() if s.status == InstanceStatus.BUSY])
        
        total_requests = sum(s.total_requests for s in self.instances.values())
        active_requests = sum(s.active_requests for s in self.instances.values())
        total_errors = sum(s.error_count for s in self.instances.values())
        
        # 计算平均响应时间（简化实现）
        avg_response_time = 0.0
        if total_requests > 0:
            # 假设每个活跃请求平均耗时1秒
            avg_response_time = active_requests * 1.0 / total_requests
        
        return {
            'total_instances': total_instances,
            'running_instances': running_instances,
            'disabled_instances': disabled_instances,
            'error_instances': error_instances,
            'busy_instances': busy_instances,
            'total_requests': total_requests,
            'active_requests': active_requests,
            'total_errors': total_errors,
            'avg_response_time': avg_response_time,
            'auth_profiles_found': len(self.discover_auth_profiles())
        }