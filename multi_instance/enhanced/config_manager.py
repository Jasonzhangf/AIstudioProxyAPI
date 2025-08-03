"""
Configuration Manager for the Enhanced Multi-Instance System.

This module handles loading, validating, and applying configuration settings.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """
    Handles loading, validating, and applying configuration settings.
    
    Responsibilities:
    - Load configuration from files and environment variables
    - Validate configuration settings
    - Apply configuration changes at runtime
    - Provide a centralized configuration interface
    """
    
    def __init__(self, 
                 config_dir: str = "multi_instance/enhanced/config",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory for configuration files
            logger: Logger instance
        """
        self.config_dir = Path(config_dir)
        self.logger = logger or logging.getLogger(__name__)
        
        # Configuration storage
        self.config: Dict[str, Any] = {}
        
        # Default configuration
        self.default_config = {
            "general": {
                "enabled": True,
                "log_level": "INFO"
            },
            "instances": {
                "auto_start": True,
                "max_instances": 5,
                "default_launch_mode": "AUTO",
                "default_max_concurrent_requests": 1
            },
            "routing": {
                "strategy": "PRIMARY_FIRST",
                "enable_failover": True,
                "request_timeout": 300,
                "max_retries": 2
            },
            "error_recovery": {
                "enabled": True,
                "max_recovery_attempts": 3,
                "interactive_mode": False,
                "save_screenshots": True
            },
            "monitoring": {
                "enabled": True,
                "metrics_interval": 60,
                "health_check_interval": 30
            }
        }
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to configuration file (optional)
            
        Returns:
            Dict[str, Any]: Loaded configuration
        """
        # Start with default configuration
        self.config = self.default_config.copy()
        
        # Determine config path
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = self.config_dir / "config.json"
        
        # Load from file if it exists
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                
                # Merge with default config
                self._merge_config(self.config, file_config)
                
                self.logger.info(f"Configuration loaded from {config_file}")
            except Exception as e:
                self.logger.error(f"Failed to load configuration from {config_file}: {e}")
        else:
            # Create default config file
            self.save_config(str(config_file))
            self.logger.info(f"Created default configuration at {config_file}")
        
        # Override with environment variables
        self._load_from_env()
        
        return self.config
    
    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]):
        """
        Recursively merge source configuration into target.
        
        Args:
            target: Target configuration
            source: Source configuration
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        # Define environment variable mappings
        env_mappings = {
            "MULTI_INSTANCE_ENABLED": ("general", "enabled", bool),
            "MULTI_INSTANCE_LOG_LEVEL": ("general", "log_level", str),
            "MULTI_INSTANCE_AUTO_START": ("instances", "auto_start", bool),
            "MULTI_INSTANCE_MAX_INSTANCES": ("instances", "max_instances", int),
            "MULTI_INSTANCE_LAUNCH_MODE": ("instances", "default_launch_mode", str),
            "MULTI_INSTANCE_MAX_REQUESTS": ("instances", "default_max_concurrent_requests", int),
            "MULTI_INSTANCE_ROUTING_STRATEGY": ("routing", "strategy", str),
            "MULTI_INSTANCE_ENABLE_FAILOVER": ("routing", "enable_failover", bool),
            "MULTI_INSTANCE_REQUEST_TIMEOUT": ("routing", "request_timeout", int),
            "MULTI_INSTANCE_MAX_RETRIES": ("routing", "max_retries", int),
            "MULTI_INSTANCE_ERROR_RECOVERY": ("error_recovery", "enabled", bool),
            "MULTI_INSTANCE_INTERACTIVE_MODE": ("error_recovery", "interactive_mode", bool),
            "MULTI_INSTANCE_MONITORING": ("monitoring", "enabled", bool)
        }
        
        # Process environment variables
        for env_var, (section, key, type_func) in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                
                # Convert value to appropriate type
                if type_func == bool:
                    value = value.lower() in ('true', 'yes', '1', 'y')
                else:
                    try:
                        value = type_func(value)
                    except ValueError:
                        self.logger.warning(f"Invalid value for {env_var}: {value}")
                        continue
                
                # Update config
                self.config[section][key] = value
                self.logger.debug(f"Config override from environment: {section}.{key} = {value}")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Any: Configuration value
        """
        # Split key into parts
        parts = key.split('.')
        
        # Navigate through config
        current = self.config
        for part in parts:
            if part not in current:
                return default
            current = current[part]
        
        return current
    
    def set_config(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            value: Value to set
        """
        # Split key into parts
        parts = key.split('.')
        
        # Navigate through config
        current = self.config
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set value
        current[parts[-1]] = value
        
        self.logger.info(f"Configuration updated: {key} = {value}")
    
    def save_config(self, config_path: Optional[str] = None) -> bool:
        """
        Save the current configuration to a file.
        
        Args:
            config_path: Path to save configuration to (optional)
            
        Returns:
            bool: True if successful
        """
        # Determine config path
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = self.config_dir / "config.json"
        
        try:
            # Ensure directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write config
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Configuration saved to {config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration to {config_file}: {e}")
            return False
    
    def reload_config(self) -> bool:
        """
        Reload configuration from the source.
        
        Returns:
            bool: True if successful
        """
        try:
            self.load_config()
            return True
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            return False