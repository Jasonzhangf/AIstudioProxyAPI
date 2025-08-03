"""
Multi-Instance Server for the Enhanced Multi-Instance System.

This module integrates all components of the Enhanced Multi-Instance System and
provides a unified interface for the rest of the application.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .instance_manager import InstanceManager
from .request_router import RequestRouter
from .error_recovery import ErrorRecovery
from .config_manager import ConfigManager
from .monitoring import MonitoringSystem


class MultiInstanceServer:
    """
    Integrates all components of the Enhanced Multi-Instance System.
    
    This class serves as the main entry point for the Enhanced Multi-Instance System,
    coordinating the interaction between the instance manager, request router,
    error recovery system, and monitoring system.
    """
    
    def __init__(self, 
                 fastapi_app: FastAPI,
                 auth_profiles_dir: str = "auth_profiles",
                 config_dir: str = "multi_instance/enhanced/config",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the multi-instance server.
        
        Args:
            fastapi_app: FastAPI application to integrate with
            auth_profiles_dir: Directory containing authentication profiles
            config_dir: Directory for configuration files
            logger: Logger instance
        """
        self.app = fastapi_app
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize components
        self.config_manager = ConfigManager(
            config_dir=config_dir,
            logger=self.logger
        )
        
        self.instance_manager = InstanceManager(
            auth_profiles_dir=auth_profiles_dir,
            config_dir=config_dir,
            logger=self.logger
        )
        
        self.request_router = RequestRouter(
            instance_manager=self.instance_manager,
            logger=self.logger
        )
        
        self.error_recovery = ErrorRecovery(
            logger=self.logger
        )
        
        self.monitoring_system = MonitoringSystem(
            logger=self.logger
        )
        
        # System state
        self.enabled = self.config_manager.get_config("general.enabled", True)
        
        # Set up routes if enabled
        if self.enabled:
            self._setup_routes()
            self.logger.info("Enhanced Multi-Instance System enabled")
        else:
            self.logger.info("Enhanced Multi-Instance System disabled")
    
    def _setup_routes(self):
        """Set up API routes."""
        # Add static files for dashboard
        dashboard_dir = Path(__file__).parent / "dashboard"
        if dashboard_dir.exists():
            self.app.mount("/static/multi-instance", StaticFiles(directory=str(dashboard_dir)), name="multi-instance-static")
        
        # Add dashboard route
        @self.app.get("/multi-instance/dashboard", response_class=HTMLResponse, tags=["multi-instance"])
        async def dashboard():
            """Multi-instance system dashboard."""
            return self._create_dashboard_html()
        
        # Add health check route
        @self.app.get("/api/multi-instance/health", tags=["multi-instance"])
        async def health_check():
            """Multi-instance system health check."""
            if not self.enabled:
                return {"enabled": False, "message": "Multi-instance system is disabled"}
            
            try:
                # Get health status from components
                instance_manager_stats = await self._get_instance_manager_stats()
                request_router_stats = await self._get_request_router_stats()
                error_recovery_stats = self.error_recovery.get_error_statistics()
                monitoring_stats = self.monitoring_system.get_metrics()
                
                return {
                    "enabled": True,
                    "status": "healthy",
                    "instance_manager": instance_manager_stats,
                    "request_router": request_router_stats,
                    "error_recovery": error_recovery_stats,
                    "monitoring": monitoring_stats
                }
            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                return {
                    "enabled": True,
                    "status": "error",
                    "message": str(e)
                }
        
        # Add instance management routes
        @self.app.get("/api/multi-instance/instances", tags=["multi-instance"])
        async def get_instances():
            """Get all instances."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            try:
                instances = {}
                for instance_id in self.instance_manager.instances:
                    instance = await self.instance_manager.get_instance(instance_id)
                    if instance:
                        health = await self.instance_manager.check_instance_health(instance_id)
                        instances[instance_id] = {
                            "config": instance.to_dict(),
                            "health": health
                        }
                
                return {"instances": instances}
            except Exception as e:
                self.logger.error(f"Failed to get instances: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/multi-instance/instances/{instance_id}/start", tags=["multi-instance"])
        async def start_instance(instance_id: str):
            """Start an instance."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            try:
                success = await self.instance_manager.start_instance(instance_id)
                if success:
                    return {"success": True, "message": f"Instance {instance_id} started successfully"}
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to start instance {instance_id}")
            except Exception as e:
                self.logger.error(f"Failed to start instance {instance_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/multi-instance/instances/{instance_id}/stop", tags=["multi-instance"])
        async def stop_instance(instance_id: str):
            """Stop an instance."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            try:
                success = await self.instance_manager.stop_instance(instance_id)
                if success:
                    return {"success": True, "message": f"Instance {instance_id} stopped successfully"}
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to stop instance {instance_id}")
            except Exception as e:
                self.logger.error(f"Failed to stop instance {instance_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/multi-instance/instances/{instance_id}/restart", tags=["multi-instance"])
        async def restart_instance(instance_id: str):
            """Restart an instance."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            try:
                success = await self.instance_manager.restart_instance(instance_id)
                if success:
                    return {"success": True, "message": f"Instance {instance_id} restarted successfully"}
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to restart instance {instance_id}")
            except Exception as e:
                self.logger.error(f"Failed to restart instance {instance_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Add configuration routes
        @self.app.get("/api/multi-instance/config", tags=["multi-instance"])
        async def get_config():
            """Get configuration."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            return self.config_manager.config
        
        @self.app.post("/api/multi-instance/config", tags=["multi-instance"])
        async def update_config(config: Dict[str, Any]):
            """Update configuration."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            try:
                # Update config
                for key, value in config.items():
                    self.config_manager.set_config(key, value)
                
                # Save config
                success = self.config_manager.save_config()
                if success:
                    return {"success": True, "message": "Configuration updated successfully"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to save configuration")
            except Exception as e:
                self.logger.error(f"Failed to update configuration: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Add monitoring routes
        @self.app.get("/api/multi-instance/metrics", tags=["multi-instance"])
        async def get_metrics():
            """Get metrics."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            return self.monitoring_system.get_metrics()
        
        @self.app.get("/api/multi-instance/metrics/{instance_id}", tags=["multi-instance"])
        async def get_instance_metrics(instance_id: str):
            """Get metrics for a specific instance."""
            if not self.enabled:
                raise HTTPException(status_code=404, detail="Multi-instance system is disabled")
            
            return self.monitoring_system.get_instance_metrics(instance_id)
    
    def _create_dashboard_html(self) -> str:
        """Create dashboard HTML."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Multi-Instance System Dashboard</title>
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
                .instance-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
                .instance-id { font-weight: bold; color: #333; }
                .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
                .status-healthy { background: #e8f5e8; color: #2e7d32; }
                .status-unhealthy { background: #ffebee; color: #c62828; }
                .status-warning { background: #fff3e0; color: #ef6c00; }
                .instance-info { margin-bottom: 15px; }
                .instance-info div { margin-bottom: 5px; font-size: 14px; color: #666; }
                .instance-actions { display: flex; gap: 10px; }
                .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; }
                .btn-primary { background: #2196f3; color: white; }
                .btn-danger { background: #f44336; color: white; }
                .btn-warning { background: #ff9800; color: white; }
                .btn:hover { opacity: 0.8; }
                .refresh-btn { position: fixed; bottom: 20px; right: 20px; background: #2196f3; color: white; border: none; border-radius: 50%; width: 60px; height: 60px; cursor: pointer; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Multi-Instance System Dashboard</h1>
                    <p>Monitor and manage AI Studio proxy instances</p>
                </div>
                
                <div class="status-grid" id="statusGrid">
                    <!-- Status cards will be loaded dynamically -->
                    <div class="status-card">
                        <h3>Loading...</h3>
                        <div class="status-value">...</div>
                    </div>
                </div>
                
                <div class="instances-grid" id="instancesGrid">
                    <!-- Instance cards will be loaded dynamically -->
                    <div class="instance-card">
                        <div class="instance-header">
                            <span class="instance-id">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <button class="refresh-btn" onclick="loadData()" title="Refresh data">🔄</button>
            
            <script>
                // Load data from API
                async function loadData() {
                    try {
                        // Get health data
                        const healthResponse = await fetch('/api/multi-instance/health');
                        const healthData = await healthResponse.json();
                        
                        // Get instances data
                        const instancesResponse = await fetch('/api/multi-instance/instances');
                        const instancesData = await instancesResponse.json();
                        
                        // Update UI
                        updateStatusCards(healthData);
                        updateInstanceCards(instancesData);
                    } catch (error) {
                        console.error('Failed to load data:', error);
                    }
                }
                
                // Update status cards
                function updateStatusCards(data) {
                    const statusGrid = document.getElementById('statusGrid');
                    
                    // Extract data
                    const instanceManager = data.instance_manager || {};
                    const requestRouter = data.request_router || {};
                    const errorRecovery = data.error_recovery || {};
                    
                    // Create HTML
                    statusGrid.innerHTML = `
                        <div class="status-card">
                            <h3>Total Instances</h3>
                            <div class="status-value">${instanceManager.total_instances || 0}</div>
                            <div class="status-label">Total configured instances</div>
                        </div>
                        <div class="status-card">
                            <h3>Available Instances</h3>
                            <div class="status-value">${instanceManager.available_instances || 0}</div>
                            <div class="status-label">Instances ready to process requests</div>
                        </div>
                        <div class="status-card">
                            <h3>Active Requests</h3>
                            <div class="status-value">${requestRouter.active_requests || 0}</div>
                            <div class="status-label">Currently processing requests</div>
                        </div>
                        <div class="status-card">
                            <h3>Success Rate</h3>
                            <div class="status-value">${(requestRouter.success_rate || 0).toFixed(1)}%</div>
                            <div class="status-label">Request success rate</div>
                        </div>
                        <div class="status-card">
                            <h3>Active Errors</h3>
                            <div class="status-value">${errorRecovery.active_errors || 0}</div>
                            <div class="status-label">Errors requiring attention</div>
                        </div>
                        <div class="status-card">
                            <h3>System Status</h3>
                            <div class="status-value">${data.status || 'unknown'}</div>
                            <div class="status-label">Overall system health</div>
                        </div>
                    `;
                }
                
                // Update instance cards
                function updateInstanceCards(data) {
                    const instancesGrid = document.getElementById('instancesGrid');
                    const instances = data.instances || {};
                    
                    // Check if there are instances
                    if (Object.keys(instances).length === 0) {
                        instancesGrid.innerHTML = `
                            <div class="instance-card">
                                <div class="instance-header">
                                    <span class="instance-id">No instances found</span>
                                </div>
                                <p>No instances are currently configured.</p>
                            </div>
                        `;
                        return;
                    }
                    
                    // Create HTML for each instance
                    let html = '';
                    for (const [instanceId, instanceData] of Object.entries(instances)) {
                        const config = instanceData.config || {};
                        const health = instanceData.health || {};
                        
                        // Determine status class
                        let statusClass = 'status-warning';
                        if (health.healthy) {
                            statusClass = 'status-healthy';
                        } else if (health.status === 'error') {
                            statusClass = 'status-unhealthy';
                        }
                        
                        html += `
                            <div class="instance-card">
                                <div class="instance-header">
                                    <span class="instance-id">${instanceId}</span>
                                    <span class="status-badge ${statusClass}">${health.status || 'unknown'}</span>
                                </div>
                                <div class="instance-info">
                                    <div><strong>Email:</strong> ${config.auth_profile?.email || 'unknown'}</div>
                                    <div><strong>Port:</strong> ${config.port || 'unknown'}</div>
                                    <div><strong>Launch Mode:</strong> ${config.launch_mode || 'unknown'}</div>
                                    <div><strong>Active Requests:</strong> ${health.active_requests || 0}/${config.max_concurrent_requests || 1}</div>
                                    <div><strong>Error Count:</strong> ${config.error_count || 0}</div>
                                </div>
                                <div class="instance-actions">
                                    <button class="btn btn-primary" onclick="controlInstance('${instanceId}', 'start')">Start</button>
                                    <button class="btn btn-danger" onclick="controlInstance('${instanceId}', 'stop')">Stop</button>
                                    <button class="btn btn-warning" onclick="controlInstance('${instanceId}', 'restart')">Restart</button>
                                </div>
                            </div>
                        `;
                    }
                    
                    instancesGrid.innerHTML = html;
                }
                
                // Control instance
                async function controlInstance(instanceId, action) {
                    try {
                        const response = await fetch(`/api/multi-instance/instances/${instanceId}/${action}`, {
                            method: 'POST'
                        });
                        
                        const data = await response.json();
                        
                        if (data.success) {
                            alert(data.message);
                            loadData();
                        } else {
                            alert(`Failed: ${data.message || 'Unknown error'}`);
                        }
                    } catch (error) {
                        alert(`Error: ${error.message}`);
                    }
                }
                
                // Load data on page load
                loadData();
                
                // Refresh data every 30 seconds
                setInterval(loadData, 30000);
            </script>
        </body>
        </html>
        """
    
    async def _get_instance_manager_stats(self) -> Dict[str, Any]:
        """Get instance manager statistics."""
        available_instances = await self.instance_manager.get_available_instances()
        
        return {
            "total_instances": len(self.instance_manager.instances),
            "available_instances": len(available_instances)
        }
    
    async def _get_request_router_stats(self) -> Dict[str, Any]:
        """Get request router statistics."""
        metrics = await self.request_router.get_metrics()
        
        return {
            "active_requests": len(self.request_router.active_requests),
            "success_rate": metrics.get("success_rate", 0),
            "average_response_time": metrics.get("average_response_time", 0),
            "routing_strategy": self.request_router.routing_strategy.value
        }
    
    async def startup(self):
        """Start the multi-instance server."""
        if not self.enabled:
            return
        
        try:
            self.logger.info("Starting Enhanced Multi-Instance System")
            
            # Initialize instance manager
            await self.instance_manager.initialize()
            
            # Start monitoring system
            monitoring_interval = self.config_manager.get_config("monitoring.metrics_interval", 60)
            await self.monitoring_system.start(interval=monitoring_interval)
            
            # Auto-start instances if configured
            auto_start = self.config_manager.get_config("instances.auto_start", True)
            if auto_start:
                await self._auto_start_instances()
            
            self.logger.info("Enhanced Multi-Instance System started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start Enhanced Multi-Instance System: {e}")
    
    async def _auto_start_instances(self):
        """Auto-start instances."""
        try:
            self.logger.info("Auto-starting instances")
            
            # Get max instances to start
            max_instances = self.config_manager.get_config("instances.max_instances", 5)
            
            # Start instances
            started_count = 0
            for instance_id in self.instance_manager.instances:
                if started_count >= max_instances:
                    break
                
                self.logger.info(f"Auto-starting instance {instance_id}")
                success = await self.instance_manager.start_instance(instance_id)
                
                if success:
                    self.logger.info(f"Instance {instance_id} started successfully")
                    started_count += 1
                else:
                    self.logger.warning(f"Failed to start instance {instance_id}")
            
            self.logger.info(f"Auto-started {started_count} instances")
            
        except Exception as e:
            self.logger.error(f"Failed to auto-start instances: {e}")
    
    async def shutdown(self):
        """Shut down the multi-instance server."""
        if not self.enabled:
            return
        
        try:
            self.logger.info("Shutting down Enhanced Multi-Instance System")
            
            # Stop monitoring system
            await self.monitoring_system.stop()
            
            # Stop all instances
            for instance_id in list(self.instance_manager.instances.keys()):
                try:
                    await self.instance_manager.stop_instance(instance_id)
                except Exception as e:
                    self.logger.error(f"Failed to stop instance {instance_id}: {e}")
            
            # Shutdown instance manager
            await self.instance_manager.shutdown()
            
            self.logger.info("Enhanced Multi-Instance System shut down successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to shut down Enhanced Multi-Instance System: {e}")
    
    async def route_request(self, request, http_request: Request) -> Tuple[str, Any]:
        """
        Route a request to an appropriate instance.
        
        Args:
            request: The request to route
            http_request: The HTTP request
            
        Returns:
            Tuple[str, Any]: Request ID and response
        """
        if not self.enabled:
            return None, None
        
        return await self.request_router.route_request(request, http_request)
    
    def is_enabled(self) -> bool:
        """Check if the multi-instance system is enabled."""
        return self.enabled