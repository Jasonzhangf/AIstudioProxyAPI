# Enhanced Multi-Instance System

This module implements a robust multi-instance system for the AI Studio Proxy API that can manage multiple browser instances, distribute requests efficiently, and provide failover capabilities.

## Features

- **Multiple Browser Instances**: Run multiple browser instances with different authentication profiles
- **Intelligent Request Routing**: Distribute requests across instances using various strategies
- **Automatic Failover**: Automatically retry requests on different instances when errors occur
- **Error Recovery**: Detect and recover from common errors
- **Monitoring Dashboard**: Web UI for monitoring and managing instances
- **Configuration Management**: Centralized configuration with environment variable overrides

## Architecture

The Enhanced Multi-Instance System consists of the following components:

- **Instance Manager**: Manages the lifecycle of browser instances
- **Request Router**: Distributes requests to appropriate instances
- **Error Recovery**: Handles error detection and recovery
- **Config Manager**: Manages configuration settings
- **Monitoring System**: Collects metrics and provides insights
- **Multi-Instance Server**: Integrates all components and provides a unified interface

## Usage

### Basic Usage

```python
from multi_instance.enhanced import MultiInstanceServer

# Create multi-instance server
multi_instance_server = MultiInstanceServer(
    fastapi_app=app,
    auth_profiles_dir="auth_profiles",
    config_dir="multi_instance/enhanced/config"
)

# Start multi-instance server
await multi_instance_server.startup()

# Route a request
request_id, response = await multi_instance_server.route_request(request, http_request)

# Shut down multi-instance server
await multi_instance_server.shutdown()
```

### Configuration

The Enhanced Multi-Instance System can be configured through the `config.json` file in the `config_dir` directory. The following configuration options are available:

```json
{
  "general": {
    "enabled": true,
    "log_level": "INFO"
  },
  "instances": {
    "auto_start": true,
    "max_instances": 5,
    "default_launch_mode": "AUTO",
    "default_max_concurrent_requests": 1
  },
  "routing": {
    "strategy": "PRIMARY_FIRST",
    "enable_failover": true,
    "request_timeout": 300,
    "max_retries": 2
  },
  "error_recovery": {
    "enabled": true,
    "max_recovery_attempts": 3,
    "interactive_mode": false,
    "save_screenshots": true
  },
  "monitoring": {
    "enabled": true,
    "metrics_interval": 60,
    "health_check_interval": 30
  }
}
```

### Environment Variables

The following environment variables can be used to override configuration settings:

- `MULTI_INSTANCE_ENABLED`: Enable/disable the multi-instance system
- `MULTI_INSTANCE_LOG_LEVEL`: Log level (INFO, DEBUG, WARNING, ERROR)
- `MULTI_INSTANCE_AUTO_START`: Auto-start instances on startup
- `MULTI_INSTANCE_MAX_INSTANCES`: Maximum number of instances to start
- `MULTI_INSTANCE_LAUNCH_MODE`: Default launch mode (AUTO, HEADLESS, DEBUG)
- `MULTI_INSTANCE_MAX_REQUESTS`: Default maximum concurrent requests per instance
- `MULTI_INSTANCE_ROUTING_STRATEGY`: Default routing strategy (PRIMARY_FIRST, LEAST_LOADED, ROUND_ROBIN, RANDOM)
- `MULTI_INSTANCE_ENABLE_FAILOVER`: Enable/disable failover
- `MULTI_INSTANCE_REQUEST_TIMEOUT`: Request timeout in seconds
- `MULTI_INSTANCE_MAX_RETRIES`: Maximum number of retries
- `MULTI_INSTANCE_ERROR_RECOVERY`: Enable/disable error recovery
- `MULTI_INSTANCE_INTERACTIVE_MODE`: Enable/disable interactive error recovery
- `MULTI_INSTANCE_MONITORING`: Enable/disable monitoring

## Dashboard

The Enhanced Multi-Instance System includes a web dashboard for monitoring and managing instances. The dashboard is available at `/multi-instance/dashboard` when the system is enabled.

## API Endpoints

The following API endpoints are available:

- `GET /api/multi-instance/health`: Get system health status
- `GET /api/multi-instance/instances`: Get all instances
- `POST /api/multi-instance/instances/{instance_id}/start`: Start an instance
- `POST /api/multi-instance/instances/{instance_id}/stop`: Stop an instance
- `POST /api/multi-instance/instances/{instance_id}/restart`: Restart an instance
- `GET /api/multi-instance/config`: Get configuration
- `POST /api/multi-instance/config`: Update configuration
- `GET /api/multi-instance/metrics`: Get metrics
- `GET /api/multi-instance/metrics/{instance_id}`: Get metrics for a specific instance