"""
Data models for the Enhanced Multi-Instance System.

This module defines the core data structures used throughout the system.
"""

import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from playwright.async_api import Browser as AsyncBrowser
from playwright.async_api import Page as AsyncPage
from playwright.async_api import BrowserContext as AsyncBrowserContext
from fastapi import Request


class InstanceStatus(Enum):
    """Status of a browser instance"""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    AUTHENTICATION_REQUIRED = "auth_required"
    RESTARTING = "restarting"
    STOPPED = "stopped"


class LaunchMode(Enum):
    """Browser launch mode"""
    HEADLESS = "headless"
    DEBUG = "debug"
    AUTO = "auto"  # Auto-select: try headless first, then debug if it fails


class ErrorType(Enum):
    """Error type classification"""
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "auth_error"
    PAGE_CRASH = "page_crash"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """Recovery action type"""
    CLICK_ELEMENT = "click_element"
    INPUT_TEXT = "input_text"
    WAIT_ELEMENT = "wait_element"
    REFRESH_PAGE = "refresh_page"
    RESTART_INSTANCE = "restart_instance"
    MANUAL_INTERVENTION = "manual_intervention"


class RoutingStrategy(Enum):
    """Strategy for routing requests to instances"""
    LEAST_LOADED = "least_loaded"
    ROUND_ROBIN = "round_robin"
    PRIMARY_FIRST = "primary_first"
    RANDOM = "random"


@dataclass
class AuthProfile:
    """Authentication profile for a browser instance"""
    profile_id: str
    email: str
    file_path: str
    last_updated: float
    is_valid: bool = True
    cookies_data: Optional[Dict] = None
    
    def to_dict(self):
        """Convert to dictionary representation"""
        return asdict(self)


@dataclass
class InstanceConfig:
    """Configuration for a browser instance"""
    instance_id: str
    auth_profile: AuthProfile
    port: int
    launch_mode: LaunchMode
    max_concurrent_requests: int = 1
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    error_count: int = 0
    restart_count: int = 0
    
    def to_dict(self):
        """Convert to dictionary representation"""
        data = asdict(self)
        data['auth_profile'] = self.auth_profile.to_dict()
        data['launch_mode'] = self.launch_mode.value
        return data


@dataclass
class InstanceRuntime:
    """Runtime state of a browser instance"""
    browser: Optional[AsyncBrowser] = None
    page: Optional[AsyncPage] = None
    context: Optional[AsyncBrowserContext] = None
    active_requests: int = 0
    last_activity: float = field(default_factory=time.time)
    ws_endpoint: Optional[str] = None
    error_handlers: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class ErrorContext:
    """Error context information"""
    error_id: str
    instance_id: str
    error_type: ErrorType
    error_message: str
    timestamp: float
    page_url: str
    screenshot_path: Optional[str] = None
    element_selector: Optional[str] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3


@dataclass
class RecoveryOption:
    """Recovery option for an error"""
    action: RecoveryAction
    description: str
    selector: Optional[str] = None
    input_value: Optional[str] = None
    confidence: float = 1.0  # Confidence level for recovery success


@dataclass
class RequestContext:
    """Context for a request being processed"""
    request_id: str
    instance_id: Optional[str]
    model_id: Optional[str]
    started_at: float
    client_ip: str
    user_agent: str
    original_request: Any  # ChatCompletionRequest
    http_request: Request
    retry_count: int = 0
    max_retries: int = 2