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
                    config = InstanceConfig(**instance_data)
                    # 将集合类型正确转换
                    config.model_whitelist = set(instance_data.get('model_whitelist', []))
                    config.model_blacklist = set(instance_data.get('model_blacklist', []))
                    self.instance_configs[config.instance_id] = config
                    
                self.routing_weights = data.get('routing_weights', {})
                    
            self.logger.info(f"已加载 {len(self.instance_configs)} 个实例配置")
        except Exception as e:
            self.logger.error(f"加载实例配置失败: {e}")
    
    def _save_instance_configs(self):
        """保存实例配置"""
        try:
            config_file = self.config_dir / "instances.json"
            data = {
                'instances': [],
                'routing_weights': self.routing_weights
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
                
            self.logger.info(f"已保存 {len(self.instance_configs)} 个实例配置")
        except Exception as e:
            self.logger.error(f"保存实例配置失败: {e}")
    
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
    
    def get_available_instances(self) -> List[str]:
        """获取可用的实例ID列表"""
        available = []
        for instance_id, state in self.instances.items():
            if (state.status == InstanceStatus.READY and 
                state.active_requests < state.config.max_concurrent_requests):
                available.append(instance_id)
        return available
    
    def select_instance_for_request(self, model_id: Optional[str] = None) -> Optional[str]:
        """为请求选择最佳实例"""
        available_instances = self.get_available_instances()
        
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
        
        # 基于负载选择实例
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
            return False
        
        config = self.instance_configs[instance_id]
        
        # 更新允许的配置项
        allowed_fields = ['enabled', 'model_whitelist', 'model_blacklist', 'max_concurrent_requests']
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field in ['model_whitelist', 'model_blacklist']:
                    setattr(config, field, set(value) if isinstance(value, list) else value)
                else:
                    setattr(config, field, value)
        
        self._save_instance_configs()
        
        # 如果实例正在运行，更新运行时状态
        if instance_id in self.instances:
            self.instances[instance_id].config = config
        
        return True
    
    def set_routing_weight(self, instance_id: str, weight: float):
        """设置实例路由权重"""
        self.routing_weights[instance_id] = weight
        self._save_instance_configs()
    
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_instances = len(self.instance_configs)
        running_instances = len([s for s in self.instances.values() if s.status == InstanceStatus.READY])
        disabled_instances = len([c for c in self.instance_configs.values() if not c.enabled])
        
        total_requests = sum(s.total_requests for s in self.instances.values())
        active_requests = sum(s.active_requests for s in self.instances.values())
        
        return {
            'total_instances': total_instances,
            'running_instances': running_instances,
            'disabled_instances': disabled_instances,
            'total_requests': total_requests,
            'active_requests': active_requests,
            'auth_profiles_found': len(self.discover_auth_profiles())
        }