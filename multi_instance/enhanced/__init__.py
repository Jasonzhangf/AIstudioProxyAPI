"""
Enhanced Multi-Instance System

This package implements a robust multi-instance system for the AI Studio Proxy API
that can manage multiple browser sessions, distribute requests efficiently, and
provide failover capabilities.
"""

from .models import (
    AuthProfile, 
    InstanceConfig, 
    InstanceStatus, 
    LaunchMode,
    InstanceRuntime,
    ErrorType,
    RecoveryAction,
    ErrorContext,
    RecoveryOption,
    RoutingStrategy,
    RequestContext
)

from .instance_manager import InstanceManager
from .request_router import RequestRouter
from .error_recovery import ErrorRecovery
from .config_manager import ConfigManager
from .monitoring import MonitoringSystem
from .multi_instance_server import MultiInstanceServer

__all__ = [
    'AuthProfile',
    'InstanceConfig',
    'InstanceStatus',
    'LaunchMode',
    'InstanceRuntime',
    'ErrorType',
    'RecoveryAction',
    'ErrorContext',
    'RecoveryOption',
    'RoutingStrategy',
    'RequestContext',
    'InstanceManager',
    'RequestRouter',
    'ErrorRecovery',
    'ConfigManager',
    'MonitoringSystem',
    'MultiInstanceServer'
]