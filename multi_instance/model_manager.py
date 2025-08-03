"""
模型管理模块
负责管理每个实例的模型白名单、黑名单和可用模型列表
"""
import json
import os
from typing import Dict, List, Set, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass, field

@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    display_name: str
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    max_tokens: int = 0
    enabled: bool = True
    category: str = "general"

class ModelManager:
    """模型管理器"""
    
    def __init__(self, 
                 config_dir: str = "multi_instance/config",
                 logger: Optional[logging.Logger] = None):
        self.config_dir = Path(config_dir)
        self.logger = logger or logging.getLogger(__name__)
        
        # 全局模型信息
        self.global_models: Dict[str, ModelInfo] = {}
        
        # 实例级模型配置
        self.instance_whitelists: Dict[str, Set[str]] = {}
        self.instance_blacklists: Dict[str, Set[str]] = {}
        
        # 预设模型分类
        self.model_categories = {
            'text': ['gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash'],
            'vision': ['gemini-pro-vision', 'gemini-1.5-pro', 'gemini-1.5-flash'],
            'code': ['gemini-pro', 'gemini-1.5-pro'],
            'reasoning': ['gemini-2.0-flash-thinking-exp']
        }
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self._load_model_configs()
    
    def _load_model_configs(self):
        """加载模型配置"""
        try:
            # 加载全局模型信息
            global_models_file = self.config_dir / "global_models.json"
            if global_models_file.exists():
                with open(global_models_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for model_data in data.get('models', []):
                        model_info = ModelInfo(**model_data)
                        self.global_models[model_info.model_id] = model_info
            
            # 加载实例级配置
            instance_models_file = self.config_dir / "instance_models.json"
            if instance_models_file.exists():
                with open(instance_models_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    for instance_id, config in data.get('instances', {}).items():
                        self.instance_whitelists[instance_id] = set(config.get('whitelist', []))
                        self.instance_blacklists[instance_id] = set(config.get('blacklist', []))
            
            self.logger.info(f"已加载 {len(self.global_models)} 个全局模型配置")
            
        except Exception as e:
            self.logger.error(f"加载模型配置失败: {e}")
    
    def _save_model_configs(self):
        """保存模型配置"""
        try:
            # 保存全局模型信息
            global_models_file = self.config_dir / "global_models.json"
            global_data = {
                'models': [
                    {
                        'model_id': model.model_id,
                        'display_name': model.display_name,
                        'description': model.description,
                        'capabilities': model.capabilities,
                        'max_tokens': model.max_tokens,
                        'enabled': model.enabled,
                        'category': model.category
                    }
                    for model in self.global_models.values()
                ]
            }
            
            with open(global_models_file, 'w', encoding='utf-8') as f:
                json.dump(global_data, f, indent=2, ensure_ascii=False)
            
            # 保存实例级配置
            instance_models_file = self.config_dir / "instance_models.json"
            instance_data = {
                'instances': {}
            }
            
            for instance_id in set(self.instance_whitelists.keys()) | set(self.instance_blacklists.keys()):
                instance_data['instances'][instance_id] = {
                    'whitelist': list(self.instance_whitelists.get(instance_id, set())),
                    'blacklist': list(self.instance_blacklists.get(instance_id, set()))
                }
            
            with open(instance_models_file, 'w', encoding='utf-8') as f:
                json.dump(instance_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info("模型配置已保存")
            
        except Exception as e:
            self.logger.error(f"保存模型配置失败: {e}")
    
    def update_global_models(self, models: List[Dict[str, Any]]):
        """更新全局模型列表"""
        for model_data in models:
            model_id = model_data.get('id', '')
            if not model_id:
                continue
            
            # 从现有模型获取额外信息或使用默认值
            existing_model = self.global_models.get(model_id)
            
            model_info = ModelInfo(
                model_id=model_id,
                display_name=model_data.get('displayName', model_id),
                description=model_data.get('description', ''),
                capabilities=model_data.get('supportedGenerationMethods', []),
                max_tokens=model_data.get('outputTokenLimit', 0),
                enabled=existing_model.enabled if existing_model else True,
                category=existing_model.category if existing_model else self._categorize_model(model_id)
            )
            
            self.global_models[model_id] = model_info
        
        self._save_model_configs()
        self.logger.info(f"已更新 {len(models)} 个全局模型")
    
    def _categorize_model(self, model_id: str) -> str:
        """根据模型ID自动分类"""
        model_id_lower = model_id.lower()
        
        if 'vision' in model_id_lower:
            return 'vision'
        elif 'code' in model_id_lower:
            return 'code'
        elif 'thinking' in model_id_lower or 'reasoning' in model_id_lower:
            return 'reasoning'
        else:
            return 'text'
    
    def get_available_models_for_instance(self, instance_id: str) -> List[Dict[str, Any]]:
        """获取实例可用的模型列表"""
        available_models = []
        
        whitelist = self.instance_whitelists.get(instance_id, set())
        blacklist = self.instance_blacklists.get(instance_id, set())
        
        for model_id, model_info in self.global_models.items():
            # 检查模型是否全局启用
            if not model_info.enabled:
                continue
            
            # 检查黑名单
            if model_id in blacklist:
                continue
            
            # 检查白名单（如果设置了白名单）
            if whitelist and model_id not in whitelist:
                continue
            
            available_models.append({
                'id': model_info.model_id,
                'displayName': model_info.display_name,
                'description': model_info.description,
                'capabilities': model_info.capabilities,
                'maxTokens': model_info.max_tokens,
                'category': model_info.category
            })
        
        return available_models
    
    def is_model_available_for_instance(self, instance_id: str, model_id: str) -> bool:
        """检查模型是否对实例可用"""
        # 检查模型是否存在且启用
        if model_id not in self.global_models or not self.global_models[model_id].enabled:
            return False
        
        # 检查黑名单
        blacklist = self.instance_blacklists.get(instance_id, set())
        if model_id in blacklist:
            return False
        
        # 检查白名单
        whitelist = self.instance_whitelists.get(instance_id, set())
        if whitelist and model_id not in whitelist:
            return False
        
        return True
    
    def add_to_instance_whitelist(self, instance_id: str, model_ids: List[str]):
        """添加模型到实例白名单"""
        if instance_id not in self.instance_whitelists:
            self.instance_whitelists[instance_id] = set()
        
        self.instance_whitelists[instance_id].update(model_ids)
        self._save_model_configs()
        
        self.logger.info(f"已添加 {len(model_ids)} 个模型到实例 {instance_id} 的白名单")
    
    def remove_from_instance_whitelist(self, instance_id: str, model_ids: List[str]):
        """从实例白名单移除模型"""
        if instance_id not in self.instance_whitelists:
            return
        
        self.instance_whitelists[instance_id].difference_update(model_ids)
        self._save_model_configs()
        
        self.logger.info(f"已从实例 {instance_id} 的白名单移除 {len(model_ids)} 个模型")
    
    def add_to_instance_blacklist(self, instance_id: str, model_ids: List[str]):
        """添加模型到实例黑名单"""
        if instance_id not in self.instance_blacklists:
            self.instance_blacklists[instance_id] = set()
        
        self.instance_blacklists[instance_id].update(model_ids)
        self._save_model_configs()
        
        self.logger.info(f"已添加 {len(model_ids)} 个模型到实例 {instance_id} 的黑名单")
    
    def remove_from_instance_blacklist(self, instance_id: str, model_ids: List[str]):
        """从实例黑名单移除模型"""
        if instance_id not in self.instance_blacklists:
            return
        
        self.instance_blacklists[instance_id].difference_update(model_ids)
        self._save_model_configs()
        
        self.logger.info(f"已从实例 {instance_id} 的黑名单移除 {len(model_ids)} 个模型")
    
    def clear_instance_whitelist(self, instance_id: str):
        """清空实例白名单"""
        if instance_id in self.instance_whitelists:
            self.instance_whitelists[instance_id].clear()
            self._save_model_configs()
            self.logger.info(f"已清空实例 {instance_id} 的白名单")
    
    def clear_instance_blacklist(self, instance_id: str):
        """清空实例黑名单"""
        if instance_id in self.instance_blacklists:
            self.instance_blacklists[instance_id].clear()
            self._save_model_configs()
            self.logger.info(f"已清空实例 {instance_id} 的黑名单")
    
    def get_instance_model_config(self, instance_id: str) -> Dict[str, Any]:
        """获取实例的模型配置"""
        whitelist = list(self.instance_whitelists.get(instance_id, set()))
        blacklist = list(self.instance_blacklists.get(instance_id, set()))
        
        return {
            'instance_id': instance_id,
            'whitelist': whitelist,
            'blacklist': blacklist,
            'available_models': self.get_available_models_for_instance(instance_id)
        }
    
    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self.global_models.get(model_id)
    
    def enable_model(self, model_id: str) -> bool:
        """启用模型"""
        if model_id not in self.global_models:
            return False
        
        self.global_models[model_id].enabled = True
        self._save_model_configs()
        return True
    
    def disable_model(self, model_id: str) -> bool:
        """禁用模型"""
        if model_id not in self.global_models:
            return False
        
        self.global_models[model_id].enabled = False
        self._save_model_configs()
        return True
    
    def get_models_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类获取模型"""
        models = []
        for model_id, model_info in self.global_models.items():
            if model_info.category == category:
                models.append({
                    'id': model_info.model_id,
                    'displayName': model_info.display_name,
                    'description': model_info.description,
                    'capabilities': model_info.capabilities,
                    'maxTokens': model_info.max_tokens,
                    'enabled': model_info.enabled,
                    'category': model_info.category
                })
        return models
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取模型统计信息"""
        total_models = len(self.global_models)
        enabled_models = len([m for m in self.global_models.values() if m.enabled])
        
        category_stats = {}
        for category in ['text', 'vision', 'code', 'reasoning']:
            category_models = [m for m in self.global_models.values() if m.category == category]
            category_stats[category] = {
                'total': len(category_models),
                'enabled': len([m for m in category_models if m.enabled])
            }
        
        instance_stats = {}
        for instance_id in set(self.instance_whitelists.keys()) | set(self.instance_blacklists.keys()):
            instance_stats[instance_id] = {
                'whitelist_count': len(self.instance_whitelists.get(instance_id, set())),
                'blacklist_count': len(self.instance_blacklists.get(instance_id, set())),
                'available_count': len(self.get_available_models_for_instance(instance_id))
            }
        
        return {
            'total_models': total_models,
            'enabled_models': enabled_models,
            'category_stats': category_stats,
            'instance_stats': instance_stats
        }
    
    def export_config(self) -> Dict[str, Any]:
        """导出完整配置"""
        return {
            'global_models': {
                model_id: {
                    'model_id': model.model_id,
                    'display_name': model.display_name,
                    'description': model.description,
                    'capabilities': model.capabilities,
                    'max_tokens': model.max_tokens,
                    'enabled': model.enabled,
                    'category': model.category
                }
                for model_id, model in self.global_models.items()
            },
            'instance_whitelists': {
                instance_id: list(whitelist)
                for instance_id, whitelist in self.instance_whitelists.items()
            },
            'instance_blacklists': {
                instance_id: list(blacklist)
                for instance_id, blacklist in self.instance_blacklists.items()
            }
        }
    
    def import_config(self, config: Dict[str, Any]) -> bool:
        """导入配置"""
        try:
            # 导入全局模型
            for model_id, model_data in config.get('global_models', {}).items():
                model_info = ModelInfo(**model_data)
                self.global_models[model_id] = model_info
            
            # 导入实例白名单
            for instance_id, whitelist in config.get('instance_whitelists', {}).items():
                self.instance_whitelists[instance_id] = set(whitelist)
            
            # 导入实例黑名单
            for instance_id, blacklist in config.get('instance_blacklists', {}).items():
                self.instance_blacklists[instance_id] = set(blacklist)
            
            self._save_model_configs()
            self.logger.info("配置导入成功")
            return True
            
        except Exception as e:
            self.logger.error(f"配置导入失败: {e}")
            return False