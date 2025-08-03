"""
多实例管理Web API
提供实例管理、模型配置、路由控制的REST API接口
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import logging
import time

from .instance_manager import MultiInstanceManager, InstanceStatus
from .model_manager import ModelManager
from .request_router import RequestRouter, RoutingStrategy

# Pydantic模型定义
class InstanceConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    max_concurrent_requests: Optional[int] = None
    model_whitelist: Optional[List[str]] = None
    model_blacklist: Optional[List[str]] = None

class ModelConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    category: Optional[str] = None
    description: Optional[str] = None

class RoutingConfigUpdate(BaseModel):
    strategy: Optional[str] = None
    enable_failover: Optional[bool] = None
    weights: Optional[Dict[str, float]] = None

def create_management_api(instance_manager: MultiInstanceManager, 
                         model_manager: ModelManager,
                         request_router: RequestRouter,
                         logger: Optional[logging.Logger] = None) -> APIRouter:
    """创建管理API路由器"""
    
    router = APIRouter(prefix="/api/management", tags=["multi-instance-management"])
    
    if not logger:
        logger = logging.getLogger(__name__)
    
    # ==================== 实例管理 ====================
    
    @router.get("/instances", summary="获取所有实例状态")
    async def get_instances():
        """获取所有实例的状态信息"""
        try:
            status = instance_manager.get_all_instances_status()
            configs = {
                instance_id: {
                    'instance_id': config.instance_id,
                    'email': config.email,
                    'auth_profile_path': config.auth_profile_path,
                    'enabled': config.enabled,
                    'port': config.port,
                    'max_concurrent_requests': config.max_concurrent_requests,
                    'created_at': config.created_at,
                    'last_used_at': config.last_used_at
                }
                for instance_id, config in instance_manager.instance_configs.items()
            }
            
            return {
                'success': True,
                'data': {
                    'running_instances': status,
                    'all_configs': configs,
                    'statistics': instance_manager.get_statistics()
                }
            }
        except Exception as e:
            logger.error(f"获取实例状态失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/instances/{instance_id}", summary="获取单个实例详情")
    async def get_instance(instance_id: str):
        """获取指定实例的详细信息"""
        try:
            if instance_id not in instance_manager.instance_configs:
                raise HTTPException(status_code=404, detail="实例不存在")
            
            config = instance_manager.instance_configs[instance_id]
            state = instance_manager.get_instance_state(instance_id)
            model_config = model_manager.get_instance_model_config(instance_id)
            
            return {
                'success': True,
                'data': {
                    'config': {
                        'instance_id': config.instance_id,
                        'email': config.email,
                        'auth_profile_path': config.auth_profile_path,
                        'enabled': config.enabled,
                        'port': config.port,
                        'max_concurrent_requests': config.max_concurrent_requests,
                        'created_at': config.created_at,
                        'last_used_at': config.last_used_at
                    },
                    'state': {
                        'status': state.status.value if state else 'stopped',
                        'active_requests': state.active_requests if state else 0,
                        'total_requests': state.total_requests if state else 0,
                        'error_count': state.error_count if state else 0,
                        'last_error': state.last_error if state else None,
                        'started_at': state.started_at if state else None,
                        'current_model_id': state.current_model_id if state else None
                    },
                    'model_config': model_config
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取实例详情失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/instances/{instance_id}", summary="更新实例配置")
    async def update_instance(instance_id: str, update: InstanceConfigUpdate):
        """更新实例配置"""
        try:
            if instance_id not in instance_manager.instance_configs:
                raise HTTPException(status_code=404, detail="实例不存在")
            
            update_data = {}
            if update.enabled is not None:
                update_data['enabled'] = update.enabled
            if update.max_concurrent_requests is not None:
                update_data['max_concurrent_requests'] = update.max_concurrent_requests
            if update.model_whitelist is not None:
                update_data['model_whitelist'] = update.model_whitelist
            if update.model_blacklist is not None:
                update_data['model_blacklist'] = update.model_blacklist
            
            success = instance_manager.update_instance_config(instance_id, **update_data)
            
            if success:
                return {'success': True, 'message': '实例配置已更新'}
            else:
                raise HTTPException(status_code=400, detail="更新实例配置失败")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新实例配置失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/instances/discover", summary="发现新的认证配置")
    async def discover_instances():
        """发现并创建新的实例配置"""
        try:
            profiles = instance_manager.discover_auth_profiles()
            new_instances = instance_manager.auto_create_instances()
            
            return {
                'success': True,
                'data': {
                    'discovered_profiles': profiles,
                    'new_instances': new_instances,
                    'total_instances': len(instance_manager.instance_configs)
                }
            }
        except Exception as e:
            logger.error(f"发现实例失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/instances/{instance_id}/enable", summary="启用实例")
    async def enable_instance(instance_id: str):
        """启用指定实例"""
        try:
            success = instance_manager.update_instance_config(instance_id, enabled=True)
            if success:
                return {'success': True, 'message': f'实例 {instance_id} 已启用'}
            else:
                raise HTTPException(status_code=404, detail="实例不存在")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"启用实例失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/instances/{instance_id}/disable", summary="禁用实例")
    async def disable_instance(instance_id: str):
        """禁用指定实例"""
        try:
            success = instance_manager.update_instance_config(instance_id, enabled=False)
            if success:
                return {'success': True, 'message': f'实例 {instance_id} 已禁用'}
            else:
                raise HTTPException(status_code=404, detail="实例不存在")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"禁用实例失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ==================== 模型管理 ====================
    
    @router.get("/models", summary="获取全局模型列表")
    async def get_models():
        """获取全局模型列表和统计信息"""
        try:
            models = []
            for model_id, model_info in model_manager.global_models.items():
                models.append({
                    'id': model_info.model_id,
                    'display_name': model_info.display_name,
                    'description': model_info.description,
                    'capabilities': model_info.capabilities,
                    'max_tokens': model_info.max_tokens,
                    'enabled': model_info.enabled,
                    'category': model_info.category
                })
            
            return {
                'success': True,
                'data': {
                    'models': models,
                    'statistics': model_manager.get_statistics()
                }
            }
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/models/categories", summary="按分类获取模型")
    async def get_models_by_category():
        """按分类获取模型"""
        try:
            categories = {}
            for category in ['text', 'vision', 'code', 'reasoning']:
                categories[category] = model_manager.get_models_by_category(category)
            
            return {
                'success': True,
                'data': categories
            }
        except Exception as e:
            logger.error(f"按分类获取模型失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/models/instances/{instance_id}", summary="获取实例可用模型")
    async def get_instance_models(instance_id: str):
        """获取指定实例的可用模型"""
        try:
            if instance_id not in instance_manager.instance_configs:
                raise HTTPException(status_code=404, detail="实例不存在")
            
            model_config = model_manager.get_instance_model_config(instance_id)
            
            return {
                'success': True,
                'data': model_config
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取实例模型失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/models/{model_id}/enable", summary="启用模型")
    async def enable_model(model_id: str):
        """启用指定模型"""
        try:
            success = model_manager.enable_model(model_id)
            if success:
                return {'success': True, 'message': f'模型 {model_id} 已启用'}
            else:
                raise HTTPException(status_code=404, detail="模型不存在")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"启用模型失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/models/{model_id}/disable", summary="禁用模型")
    async def disable_model(model_id: str):
        """禁用指定模型"""
        try:
            success = model_manager.disable_model(model_id)
            if success:
                return {'success': True, 'message': f'模型 {model_id} 已禁用'}
            else:
                raise HTTPException(status_code=404, detail="模型不存在")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"禁用模型失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/models/instances/{instance_id}/whitelist", summary="添加到实例白名单")
    async def add_to_whitelist(instance_id: str, model_ids: List[str]):
        """添加模型到实例白名单"""
        try:
            if instance_id not in instance_manager.instance_configs:
                raise HTTPException(status_code=404, detail="实例不存在")
            
            model_manager.add_to_instance_whitelist(instance_id, model_ids)
            return {'success': True, 'message': f'已添加 {len(model_ids)} 个模型到白名单'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"添加到白名单失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/models/instances/{instance_id}/blacklist", summary="添加到实例黑名单")
    async def add_to_blacklist(instance_id: str, model_ids: List[str]):
        """添加模型到实例黑名单"""
        try:
            if instance_id not in instance_manager.instance_configs:
                raise HTTPException(status_code=404, detail="实例不存在")
            
            model_manager.add_to_instance_blacklist(instance_id, model_ids)
            return {'success': True, 'message': f'已添加 {len(model_ids)} 个模型到黑名单'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"添加到黑名单失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/models/instances/{instance_id}/whitelist", summary="清空实例白名单")
    async def clear_whitelist(instance_id: str):
        """清空实例白名单"""
        try:
            if instance_id not in instance_manager.instance_configs:
                raise HTTPException(status_code=404, detail="实例不存在")
            
            model_manager.clear_instance_whitelist(instance_id)
            return {'success': True, 'message': '白名单已清空'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"清空白名单失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/models/instances/{instance_id}/blacklist", summary="清空实例黑名单")
    async def clear_blacklist(instance_id: str):
        """清空实例黑名单"""
        try:
            if instance_id not in instance_manager.instance_configs:
                raise HTTPException(status_code=404, detail="实例不存在")
            
            model_manager.clear_instance_blacklist(instance_id)
            return {'success': True, 'message': '黑名单已清空'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"清空黑名单失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ==================== 路由管理 ====================
    
    @router.get("/routing", summary="获取路由状态")
    async def get_routing_status():
        """获取路由器状态和统计信息"""
        try:
            return {
                'success': True,
                'data': {
                    'statistics': request_router.get_routing_statistics(),
                    'active_requests': request_router.get_active_requests(),
                    'health_status': request_router.get_health_status(),
                    'configuration': {
                        'default_strategy': request_router.default_strategy.value,
                        'enable_failover': request_router.enable_failover,
                        'request_timeout': request_router.request_timeout
                    }
                }
            }
        except Exception as e:
            logger.error(f"获取路由状态失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/routing/config", summary="更新路由配置")
    async def update_routing_config(config: RoutingConfigUpdate):
        """更新路由配置"""
        try:
            if config.strategy:
                try:
                    strategy = RoutingStrategy(config.strategy)
                    request_router.set_routing_strategy(strategy)
                except ValueError:
                    raise HTTPException(status_code=400, detail="无效的路由策略")
            
            if config.enable_failover is not None:
                request_router.enable_failover = config.enable_failover
            
            if config.weights:
                for instance_id, weight in config.weights.items():
                    instance_manager.set_routing_weight(instance_id, weight)
            
            return {'success': True, 'message': '路由配置已更新'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新路由配置失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/routing/reset-stats", summary="重置路由统计")
    async def reset_routing_stats():
        """重置路由统计信息"""
        try:
            request_router.reset_statistics()
            return {'success': True, 'message': '路由统计已重置'}
        except Exception as e:
            logger.error(f"重置路由统计失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/routing/cleanup", summary="清理过期请求")
    async def cleanup_expired_requests():
        """清理过期请求"""
        try:
            request_router.cleanup_expired_requests()
            return {'success': True, 'message': '过期请求已清理'}
        except Exception as e:
            logger.error(f"清理过期请求失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ==================== 系统管理 ====================
    
    @router.get("/health", summary="获取系统健康状态")
    async def get_health():
        """获取整个多实例系统的健康状态"""
        try:
            return {
                'success': True,
                'data': {
                    'timestamp': time.time(),
                    'instance_manager': instance_manager.get_statistics(),
                    'model_manager': model_manager.get_statistics(),
                    'request_router': request_router.get_health_status()
                }
            }
        except Exception as e:
            logger.error(f"获取健康状态失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/config/export", summary="导出配置")
    async def export_config():
        """导出完整的多实例配置"""
        try:
            return {
                'success': True,
                'data': {
                    'timestamp': time.time(),
                    'instances': {
                        instance_id: {
                            'instance_id': config.instance_id,
                            'email': config.email,
                            'enabled': config.enabled,
                            'port': config.port,
                            'max_concurrent_requests': config.max_concurrent_requests
                        }
                        for instance_id, config in instance_manager.instance_configs.items()
                    },
                    'models': model_manager.export_config(),
                    'routing_weights': instance_manager.routing_weights
                }
            }
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router