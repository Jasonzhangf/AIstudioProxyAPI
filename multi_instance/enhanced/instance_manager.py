"""
Instance Manager for the Enhanced Multi-Instance System.

This module is responsible for the lifecycle of browser instances, including
initialization, monitoring, health checks, and shutdown.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from playwright.async_api import Page as AsyncPage

from .models import (
    AuthProfile,
    InstanceConfig,
    InstanceStatus,
    LaunchMode,
    InstanceRuntime
)


class InstanceManager:
    """
    Manages the lifecycle of browser instances.
    
    Responsibilities:
    - Load authentication profiles from the auth_profiles directory
    - Launch and initialize browser instances with appropriate profiles
    - Monitor the health and status of each instance
    - Provide an interface for starting, stopping, and restarting instances
    - Maintain a registry of available instances and their capabilities
    """
    
    def __init__(self, 
                 auth_profiles_dir: str = "auth_profiles",
                 config_dir: str = "multi_instance/enhanced/config",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the instance manager.
        
        Args:
            auth_profiles_dir: Directory containing authentication profiles
            config_dir: Directory for configuration files
            logger: Logger instance
        """
        self.auth_profiles_dir = Path(auth_profiles_dir)
        self.config_dir = Path(config_dir)
        self.logger = logger or logging.getLogger(__name__)
        
        # Instance configuration and runtime state
        self.instances: Dict[str, InstanceConfig] = {}
        self.runtime_states: Dict[str, InstanceRuntime] = {}
        
        # Authentication profile management
        self.auth_profiles: Dict[str, AuthProfile] = {}
        
        # Error recovery configuration
        self.max_restart_attempts = 3
        self.restart_delay = 5.0
        self.auth_retry_delay = 10.0
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> bool:
        """
        Initialize the instance manager and load configurations.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            # Load authentication profiles
            await self.load_auth_profiles()
            
            # Load instance configurations
            self._load_instance_configs()
            
            self.logger.info(f"Instance manager initialized with {len(self.auth_profiles)} profiles and {len(self.instances)} instances")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize instance manager: {e}")
            return False
    
    async def load_auth_profiles(self) -> List[AuthProfile]:
        """
        Load authentication profiles from the auth_profiles directory.
        
        Returns:
            List[AuthProfile]: List of loaded authentication profiles
        """
        self.auth_profiles.clear()
        profiles = []
        
        try:
            # Scan multi-instance auth directory
            multi_auth_dir = self.auth_profiles_dir / "multi"
            if not multi_auth_dir.exists():
                multi_auth_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created multi-instance auth directory: {multi_auth_dir}")
            
            # Load profiles from the directory
            for auth_file in multi_auth_dir.glob("*.json"):
                try:
                    with open(auth_file, 'r', encoding='utf-8') as f:
                        auth_data = json.load(f)
                    
                    # Extract email from filename
                    email = self._extract_email_from_filename(auth_file.name)
                    
                    profile = AuthProfile(
                        profile_id=auth_file.stem,
                        email=email,
                        file_path=str(auth_file),
                        last_updated=auth_file.stat().st_mtime,
                        cookies_data=auth_data
                    )
                    
                    self.auth_profiles[email] = profile
                    profiles.append(profile)
                    self.logger.debug(f"Loaded auth profile: {email}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to load auth file {auth_file}: {e}")
            
            self.logger.info(f"Loaded {len(profiles)} authentication profiles")
            return profiles
            
        except Exception as e:
            self.logger.error(f"Failed to load authentication profiles: {e}")
            return []
    
    def _extract_email_from_filename(self, filename: str) -> str:
        """
        Extract email address from filename.
        
        Args:
            filename: Filename to extract email from
            
        Returns:
            str: Extracted email address
        """
        # Remove extension
        name = filename.replace('.json', '')
        
        # Handle common filename formats
        if '_at_' in name:
            # jason_zhangfan_at_gmail_com_0718_1752807696 -> jason.zhangfan@gmail.com
            parts = name.split('_')
            at_index = parts.index('at')
            
            user_parts = parts[:at_index]
            domain_parts = parts[at_index+1:]
            
            # Remove timestamp parts
            domain_parts = [p for p in domain_parts if not p.isdigit()]
            
            user = '.'.join(user_parts)
            domain = '.'.join(domain_parts)
            
            return f"{user}@{domain}"
        elif '@' in name:
            # Filename directly contains @ symbol
            return name.split('_')[0]  # Remove potential suffix
        else:
            # Default to filename
            return name
    
    def _load_instance_configs(self):
        """Load instance configurations from file or create defaults."""
        config_file = self.config_dir / "instances.json"
        
        if not config_file.exists():
            self._create_default_instance_configs()
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for instance_data in data.get('instances', []):
                instance_id = instance_data['instance_id']
                email = instance_data['email']
                
                # Find corresponding auth profile
                auth_profile = self.auth_profiles.get(email)
                if not auth_profile:
                    self.logger.warning(f"Auth profile for {email} not found for instance {instance_id}")
                    continue
                
                config = InstanceConfig(
                    instance_id=instance_id,
                    auth_profile=auth_profile,
                    port=instance_data['port'],
                    launch_mode=LaunchMode(instance_data.get('launch_mode', 'AUTO')),
                    max_concurrent_requests=instance_data.get('max_concurrent_requests', 1),
                    created_at=instance_data.get('created_at', time.time()),
                    last_used_at=instance_data.get('last_used_at', time.time())
                )
                
                self.instances[instance_id] = config
                self.runtime_states[instance_id] = InstanceRuntime()
                
        except Exception as e:
            self.logger.error(f"Failed to load instance configs: {e}")
    
    def _create_default_instance_configs(self):
        """Create default instance configurations."""
        port_start = 9222
        instance_num = 1
        
        for email, auth_profile in self.auth_profiles.items():
            instance_id = f"instance_{instance_num}_{email.replace('@', '_at_').replace('.', '_')}"
            
            config = InstanceConfig(
                instance_id=instance_id,
                auth_profile=auth_profile,
                port=port_start + instance_num - 1,
                launch_mode=LaunchMode.AUTO,
                created_at=time.time(),
                last_used_at=time.time()
            )
            
            self.instances[instance_id] = config
            self.runtime_states[instance_id] = InstanceRuntime()
            
            instance_num += 1
        
        # Save configurations
        self._save_instance_configs()
    
    def _save_instance_configs(self):
        """Save instance configurations to file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            config_data = {
                "instances": [
                    {
                        "instance_id": config.instance_id,
                        "email": config.auth_profile.email,
                        "port": config.port,
                        "launch_mode": config.launch_mode.value,
                        "max_concurrent_requests": config.max_concurrent_requests,
                        "created_at": config.created_at,
                        "last_used_at": config.last_used_at
                    }
                    for config in self.instances.values()
                ]
            }
            
            config_file = self.config_dir / "instances.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Failed to save instance configs: {e}")
    
    async def launch_instance(self, profile: AuthProfile) -> str:
        """
        Launch a new browser instance with the given profile.
        
        Args:
            profile: Authentication profile to use
            
        Returns:
            str: Instance ID if successful, empty string otherwise
        """
        # Generate a unique instance ID
        instance_id = f"instance_{int(time.time())}_{profile.email.replace('@', '_at_').replace('.', '_')}"
        
        # Create instance configuration
        port = 9222 + len(self.instances)
        config = InstanceConfig(
            instance_id=instance_id,
            auth_profile=profile,
            port=port,
            launch_mode=LaunchMode.AUTO
        )
        
        # Add to instances
        self.instances[instance_id] = config
        self.runtime_states[instance_id] = InstanceRuntime()
        
        # Save configuration
        self._save_instance_configs()
        
        # Start the instance
        success = await self.start_instance(instance_id)
        
        if success:
            return instance_id
        else:
            # Clean up if failed
            del self.instances[instance_id]
            del self.runtime_states[instance_id]
            self._save_instance_configs()
            return ""
    
    async def get_instance(self, instance_id: str) -> Optional[InstanceConfig]:
        """
        Get a specific browser instance by ID.
        
        Args:
            instance_id: ID of the instance to get
            
        Returns:
            Optional[InstanceConfig]: Instance configuration if found
        """
        return self.instances.get(instance_id)
    
    async def get_available_instances(self) -> List[str]:
        """
        Get a list of available browser instances.
        
        Returns:
            List[str]: List of available instance IDs
        """
        available = []
        for instance_id, config in self.instances.items():
            if instance_id in self.runtime_states:
                runtime = self.runtime_states[instance_id]
                if runtime.page and runtime.active_requests < config.max_concurrent_requests:
                    available.append(instance_id)
        return available
    
    async def start_instance(self, instance_id: str) -> bool:
        """
        Start a specific browser instance.
        
        Args:
            instance_id: ID of the instance to start
            
        Returns:
            bool: True if successful
        """
        if instance_id not in self.instances:
            self.logger.error(f"Instance {instance_id} not found")
            return False
        
        config = self.instances[instance_id]
        
        try:
            self.logger.info(f"Starting instance {instance_id}")
            
            # TODO: Implement actual browser launch logic
            # This is a placeholder for the actual implementation
            
            # Update instance status
            config.last_used_at = time.time()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start instance {instance_id}: {e}")
            return False
    
    async def stop_instance(self, instance_id: str) -> bool:
        """
        Stop a specific browser instance.
        
        Args:
            instance_id: ID of the instance to stop
            
        Returns:
            bool: True if successful
        """
        if instance_id not in self.instances:
            self.logger.error(f"Instance {instance_id} not found")
            return False
        
        try:
            runtime = self.runtime_states[instance_id]
            
            # Close page if it exists
            if runtime.page:
                await runtime.page.close()
            
            # Close context if it exists
            if runtime.context:
                await runtime.context.close()
            
            # Close browser if it exists
            if runtime.browser:
                await runtime.browser.close()
            
            # Reset runtime state
            self.runtime_states[instance_id] = InstanceRuntime()
            
            self.logger.info(f"Stopped instance {instance_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop instance {instance_id}: {e}")
            return False
    
    async def restart_instance(self, instance_id: str) -> bool:
        """
        Restart a specific browser instance.
        
        Args:
            instance_id: ID of the instance to restart
            
        Returns:
            bool: True if successful
        """
        if instance_id not in self.instances:
            self.logger.error(f"Instance {instance_id} not found")
            return False
        
        try:
            # Stop the instance
            await self.stop_instance(instance_id)
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Start the instance
            success = await self.start_instance(instance_id)
            
            if success:
                self.instances[instance_id].restart_count += 1
                self.logger.info(f"Restarted instance {instance_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to restart instance {instance_id}: {e}")
            return False
    
    async def check_instance_health(self, instance_id: str) -> Dict[str, Any]:
        """
        Check the health of a specific instance.
        
        Args:
            instance_id: ID of the instance to check
            
        Returns:
            Dict[str, Any]: Health status information
        """
        if instance_id not in self.instances:
            return {"status": "not_found", "healthy": False}
        
        config = self.instances[instance_id]
        runtime = self.runtime_states[instance_id]
        
        try:
            # Check if browser and page are available
            browser_available = runtime.browser is not None
            page_available = runtime.page is not None
            
            # Check if page is responsive
            page_responsive = False
            if page_available:
                try:
                    # Try to evaluate a simple expression
                    await runtime.page.evaluate("1 + 1")
                    page_responsive = True
                except Exception:
                    page_responsive = False
            
            # Determine overall health
            healthy = browser_available and page_available and page_responsive
            
            return {
                "status": "healthy" if healthy else "unhealthy",
                "healthy": healthy,
                "browser_available": browser_available,
                "page_available": page_available,
                "page_responsive": page_responsive,
                "active_requests": runtime.active_requests,
                "max_concurrent_requests": config.max_concurrent_requests,
                "last_activity": runtime.last_activity,
                "error_count": config.error_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to check health of instance {instance_id}: {e}")
            return {
                "status": "error",
                "healthy": False,
                "error": str(e)
            }
    
    async def shutdown(self) -> None:
        """Shutdown all instances and cleanup resources."""
        for instance_id in list(self.instances.keys()):
            try:
                await self.stop_instance(instance_id)
            except Exception as e:
                self.logger.error(f"Error stopping instance {instance_id} during shutdown: {e}")
        
        self.logger.info("Instance manager shutdown complete")