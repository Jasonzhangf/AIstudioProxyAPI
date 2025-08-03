"""
多实例服务器主模块
集成智能多实例管理功能到主服务器
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .smart_instance_manager import SmartInstanceManager
from .smart_request_router import SmartRequestRouter
from .dynamic_error_recovery import DynamicErrorRecovery
from .model_manager import ModelManager
from .web_api import create_management_api

class MultiInstanceServer:
    """智能多实例服务器"""
    
    def __init__(self, 
                 fastapi_app: FastAPI,
                 auth_profiles_dir: str = "auth_profiles",
                 config_dir: str = "multi_instance/config",
                 logger: Optional[logging.Logger] = None):
        
        self.app = fastapi_app
        self.logger = logger or logging.getLogger(__name__)
        
        # 初始化智能管理器
        self.instance_manager = SmartInstanceManager(
            auth_profiles_dir=auth_profiles_dir,
            config_dir=config_dir,
            logger=self.logger
        )
        
        self.request_router = SmartRequestRouter(
            instance_manager=self.instance_manager,
            logger=self.logger
        )
        
        self.error_recovery = DynamicErrorRecovery(
            logger=self.logger
        )
        
        self.model_manager = ModelManager(
            config_dir=config_dir,
            logger=self.logger
        )
        
        # 启用状态 - 支持环境变量或命令行参数
        self.enabled = os.environ.get('ENABLE_MULTI_INSTANCE', 'false').lower() == 'true'
        
        if self.enabled:
            self._setup_routes()
            self.logger.info("智能多实例管理已启用")
        else:
            self.logger.info("多实例管理已禁用")
    
    def _setup_routes(self):
        """设置路由"""
        
        # 添加管理API路由
        try:
            management_api = create_management_api(
                self.instance_manager,
                self.model_manager, 
                self.request_router,
                self.logger
            )
            self.app.include_router(management_api)
        except Exception as e:
            self.logger.warning(f"创建管理API失败，使用简化版本: {e}")
        
        # 添加静态文件服务（如果需要）
        templates_dir = Path(__file__).parent / "templates"
        if templates_dir.exists():
            self.app.mount("/static/multi-instance", StaticFiles(directory=str(templates_dir)), name="multi-instance-static")
        
        # 添加Web管理界面路由
        @self.app.get("/management", response_class=HTMLResponse, tags=["multi-instance"])
        async def management_ui():
            """多实例管理Web界面"""
            return self._create_management_ui()
        
        # 添加健康检查路由
        @self.app.get("/api/multi-instance/health", tags=["multi-instance"])
        async def multi_instance_health():
            """多实例系统健康检查"""
            if not self.enabled:
                return {"enabled": False, "message": "多实例管理未启用"}
            
            try:
                health_data = {
                    "enabled": True,
                    "instance_manager": self.instance_manager.get_statistics(),
                    "request_router": self.request_router.get_health_status(),
                    "error_recovery": self.error_recovery.get_error_statistics()
                }
                return health_data
            except Exception as e:
                self.logger.error(f"获取多实例健康状态失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # 添加实例控制路由
        @self.app.post("/api/multi-instance/instances/{instance_id}/start", tags=["multi-instance"])
        async def start_instance(instance_id: str):
            """启动实例"""
            try:
                success = await self.instance_manager.start_instance(instance_id)
                return {"success": success, "message": f"实例 {instance_id} {'启动成功' if success else '启动失败'}"}
            except Exception as e:
                self.logger.error(f"启动实例失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/multi-instance/instances/{instance_id}/stop", tags=["multi-instance"])
        async def stop_instance(instance_id: str):
            """停止实例"""
            try:
                await self.instance_manager.stop_instance(instance_id)
                return {"success": True, "message": f"实例 {instance_id} 已停止"}
            except Exception as e:
                self.logger.error(f"停止实例失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/multi-instance/instances/{instance_id}/debug", tags=["multi-instance"])
        async def enable_debug_mode(instance_id: str):
            """启用实例调试模式"""
            try:
                success = await self.instance_manager.enable_debug_mode(instance_id)
                self.error_recovery.enable_interactive_mode(instance_id)
                return {"success": success, "message": f"实例 {instance_id} 调试模式已启用"}
            except Exception as e:
                self.logger.error(f"启用调试模式失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # 添加错误恢复路由
        @self.app.get("/api/multi-instance/errors", tags=["multi-instance"])
        async def get_error_statistics():
            """获取错误统计"""
            return self.error_recovery.get_error_statistics()
        
        # 添加实例详情路由
        @self.app.get("/api/multi-instance/instances", tags=["multi-instance"])
        async def get_instances():
            """获取所有实例详情"""
            try:
                instances = {}
                for instance_id, config in self.instance_manager.instances.items():
                    status = self.instance_manager.get_instance_status(instance_id)
                    instances[instance_id] = {
                        "config": config.to_dict(),
                        "status": status
                    }
                return {"instances": instances}
            except Exception as e:
                self.logger.error(f"获取实例详情失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # 注意：不重写聊天完成路由，避免与现有路由冲突
        # 智能路由将通过 route_request 方法被现有系统调用
    
    def _create_management_ui(self) -> str:
        """创建管理界面HTML"""
        return """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>智能多实例管理</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
                .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .header h1 { color: #333; margin-bottom: 10px; }
                .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
                .status-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .status-card h3 { color: #666; margin-bottom: 15px; font-size: 14px; text-transform: uppercase; }
                .status-value { font-size: 24px; font-weight: bold; color: #333; }
                .status-label { font-size: 12px; color: #999; margin-top: 5px; }
                .instances-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
                .instance-card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .instance-header { display: flex; justify-content: between; align-items: center; margin-bottom: 15px; }
                .instance-id { font-weight: bold; color: #333; }
                .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
                .status-ready { background: #e8f5e8; color: #2e7d32; }
                .status-error { background: #ffebee; color: #c62828; }
                .status-busy { background: #fff3e0; color: #ef6c00; }
                .status-stopped { background: #f5f5f5; color: #666; }
                .instance-info { margin-bottom: 15px; }
                .instance-info div { margin-bottom: 5px; font-size: 14px; color: #666; }
                .instance-actions { display: flex; gap: 10px; }
                .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; }
                .btn-primary { background: #2196f3; color: white; }
                .btn-success { background: #4caf50; color: white; }
                .btn-danger { background: #f44336; color: white; }
                .btn-warning { background: #ff9800; color: white; }
                .btn:hover { opacity: 0.8; }
                .refresh-btn { position: fixed; bottom: 20px; right: 20px; background: #2196f3; color: white; border: none; border-radius: 50%; width: 60px; height: 60px; cursor: pointer; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 智能多实例管理系统</h1>
                    <p>实时监控和管理AI Studio代理实例</p>
                </div>
                
                <div class="status-grid" id="statusGrid">
                    <!-- 状态卡片将通过JavaScript动态加载 -->
                </div>
                
                <div class="instances-grid" id="instancesGrid">
                    <!-- 实例卡片将通过JavaScript动态加载 -->
                </div>
            </div>
            
            <button class="refresh-btn" onclick="loadData()" title="刷新数据">🔄</button>
            
            <script>
                async function loadData() {
                    try {
                        const response = await fetch('/api/multi-instance/health');
                        const data = await response.json();
                        
                        updateStatusCards(data);
                        updateInstanceCards(data);
                    } catch (error) {
                        console.error('加载数据失败:', error);
                    }
                }
                
                function updateStatusCards(data) {
                    const statusGrid = document.getElementById('statusGrid');
                    const stats = data.instance_manager || {};
                    const routerStats = data.request_router || {};
                    const errorStats = data.error_recovery || {};
                    
                    statusGrid.innerHTML = `
                        <div class="status-card">
                            <h3>总实例数</h3>
                            <div class="status-value">${stats.total_instances || 0}</div>
                            <div class="status-label">配置的实例总数</div>
                        </div>
                        <div class="status-card">
                            <h3>运行实例</h3>
                            <div class="status-value">${stats.running_instances || 0}</div>
                            <div class="status-label">正在运行的实例</div>
                        </div>
                        <div class="status-card">
                            <h3>可用实例</h3>
                            <div class="status-value">${stats.available_instances || 0}</div>
                            <div class="status-label">可处理请求的实例</div>
                        </div>
                        <div class="status-card">
                            <h3>系统状态</h3>
                            <div class="status-value">${routerStats.status || 'unknown'}</div>
                            <div class="status-label">整体健康状态</div>
                        </div>
                        <div class="status-card">
                            <h3>活跃错误</h3>
                            <div class="status-value">${errorStats.active_errors || 0}</div>
                            <div class="status-label">需要处理的错误</div>
                        </div>
                        <div class="status-card">
                            <h3>成功率</h3>
                            <div class="status-value">${(routerStats.success_rate || 0).toFixed(1)}%</div>
                            <div class="status-label">请求成功率</div>
                        </div>
                    `;
                }
                
                async function updateInstanceCards(data) {
                    try {
                        const response = await fetch('/api/multi-instance/instances');
                        const instanceData = await response.json();
                        const instances = instanceData.instances || {};
                        
                        const instancesGrid = document.getElementById('instancesGrid');
                        
                        if (Object.keys(instances).length === 0) {
                            instancesGrid.innerHTML = `
                                <div class="instance-card">
                                    <div class="instance-header">
                                        <span class="instance-id">暂无实例</span>
                                    </div>
                                    <p>请检查认证配置文件或启动实例</p>
                                </div>
                            `;
                            return;
                        }
                        
                        let html = '';
                        for (const [instanceId, instanceInfo] of Object.entries(instances)) {
                            const config = instanceInfo.config;
                            const status = instanceInfo.status;
                            const statusClass = status ? `status-${status.status}` : 'status-stopped';
                            const statusText = status ? status.status : 'stopped';
                            
                            html += `
                                <div class="instance-card">
                                    <div class="instance-header">
                                        <span class="instance-id">${instanceId}</span>
                                        <span class="status-badge ${statusClass}">${statusText.toUpperCase()}</span>
                                    </div>
                                    <div class="instance-info">
                                        <div><strong>邮箱:</strong> ${config.auth_profile.email}</div>
                                        <div><strong>端口:</strong> ${config.port}</div>
                                        <div><strong>模式:</strong> ${config.launch_mode}</div>
                                        <div><strong>状态:</strong> ${config.status}</div>
                                        ${status ? `<div><strong>活跃请求:</strong> ${status.active_requests}/${config.max_concurrent_requests}</div>` : ''}
                                    </div>
                                    <div class="instance-actions">
                                        <button class="btn btn-primary" onclick="controlInstance('${instanceId}', 'start')">启动</button>
                                        <button class="btn btn-danger" onclick="controlInstance('${instanceId}', 'stop')">停止</button>
                                        <button class="btn btn-warning" onclick="controlInstance('${instanceId}', 'debug')">调试</button>
                                    </div>
                                </div>
                            `;
                        }
                        
                        instancesGrid.innerHTML = html;
                    } catch (error) {
                        console.error('获取实例详情失败:', error);
                        const instancesGrid = document.getElementById('instancesGrid');
                        instancesGrid.innerHTML = `
                            <div class="instance-card">
                                <div class="instance-header">
                                    <span class="instance-id">加载失败</span>
                                </div>
                                <p>无法获取实例详情: ${error.message}</p>
                            </div>
                        `;
                    }
                }
                
                async function controlInstance(instanceId, action) {
                    try {
                        const response = await fetch(`/api/multi-instance/instances/${instanceId}/${action}`, {
                            method: 'POST'
                        });
                        const result = await response.json();
                        
                        if (result.success) {
                            alert(result.message);
                            loadData(); // 刷新数据
                        } else {
                            alert('操作失败: ' + result.message);
                        }
                    } catch (error) {
                        alert('操作失败: ' + error.message);
                    }
                }
                
                // 页面加载时获取数据
                loadData();
                
                // 每30秒自动刷新
                setInterval(loadData, 30000);
            </script>
        </body>
        </html>
        """
    
    async def startup(self):
        """启动时初始化"""
        if not self.enabled:
            return
        
        try:
            self.logger.info("启动智能多实例管理系统...")
            
            # 设置默认路由策略
            from .smart_request_router import RoutingStrategy
            strategy_name = os.environ.get('DEFAULT_ROUTING_STRATEGY', 'primary_first')
            try:
                strategy = RoutingStrategy(strategy_name)
                self.request_router.routing_strategy = strategy
                self.logger.info(f"路由策略设置为: {strategy.value}")
            except ValueError:
                self.logger.warning(f"无效的路由策略: {strategy_name}, 使用默认策略")
            
            # 启动实例（如果配置为自动启动）
            auto_start = os.environ.get('AUTO_START_INSTANCES', 'false').lower() == 'true'
            if auto_start:
                await self._auto_start_instances()
            
            self.logger.info("智能多实例服务器启动完成")
            
        except Exception as e:
            self.logger.error(f"多实例服务器启动失败: {e}")
    
    async def _auto_start_instances(self):
        """自动启动实例，失败时自动重试"""
        try:
            for instance_id in self.instance_manager.instances.keys():
                self.logger.info(f"尝试自动启动实例: {instance_id}")
                
                # 尝试启动实例，最多重试3次
                max_retries = 3
                retry_delay = 5  # 重试间隔5秒
                success = False
                
                for attempt in range(1, max_retries + 1):
                    self.logger.info(f"实例 {instance_id} 启动尝试 {attempt}/{max_retries}")
                    success = await self.instance_manager.start_instance(instance_id)
                    
                    if success:
                        self.logger.info(f"实例 {instance_id} 自动启动成功 (尝试 {attempt}/{max_retries})")
                        break
                    else:
                        if attempt < max_retries:
                            self.logger.warning(f"实例 {instance_id} 启动失败，{retry_delay}秒后重试...")
                            await asyncio.sleep(retry_delay)
                        else:
                            self.logger.error(f"实例 {instance_id} 启动失败，已达到最大重试次数 ({max_retries})")
                
                # 记录最终结果
                if not success:
                    self.logger.error(f"实例 {instance_id} 自动启动失败，已尝试 {max_retries} 次")
                    
        except Exception as e:
            self.logger.error(f"自动启动实例失败: {e}")
    

    
    async def shutdown(self):
        """关闭时清理"""
        if not self.enabled:
            return
        
        try:
            # 停止所有实例
            for instance_id in list(self.instance_manager.instances.keys()):
                await self.instance_manager.stop_instance(instance_id)
            
            self.logger.info("智能多实例服务器已关闭")
            
        except Exception as e:
            self.logger.error(f"多实例服务器关闭失败: {e}")
    
    def is_enabled(self) -> bool:
        """检查多实例管理是否启用"""
        return self.enabled
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        if not self.enabled:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "instance_manager": self.instance_manager.get_statistics(),
            "request_router": self.request_router.get_statistics(),
            "error_recovery": self.error_recovery.get_error_statistics()
        }
    
    async def route_request(self, request, http_request) -> tuple:
        """路由请求到合适的实例"""
        if not self.enabled:
            return None, None
        
        return await self.request_router.route_request(request, http_request)
    
    def get_available_instances(self) -> List[str]:
        """获取可用实例列表"""
        if not self.enabled:
            return []
        
        return self.instance_manager.get_available_instances()
    
    def get_instance_status(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """获取实例状态"""
        if not self.enabled:
            return None
        
        return self.instance_manager.get_instance_status(instance_id)