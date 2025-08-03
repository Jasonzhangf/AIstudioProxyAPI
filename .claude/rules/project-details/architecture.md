# Project Architecture Details

This file contains detailed architecture documentation extracted from the project's architecture guide.

## Core Design Principles

### Module Separation
- Divide functionality by domain to avoid circular dependencies
- Each module focuses on a specific functional area
- Use the `config/` module for unified configuration management
- Manage component dependencies through `dependencies.py`
- Prioritize asynchronous programming for performance

## Detailed Module Structure

### api_utils/ - FastAPI Application Core

#### app.py - Application Entry Point
- FastAPI application creation and configuration
- Lifecycle management (startup/shutdown)
- Middleware configuration (API key authentication)
- Global state initialization

#### routes.py - API Routes
- `/v1/chat/completions` - Chat completion endpoint
- `/v1/models` - Model list endpoint
- `/api/keys/*` - API key management endpoints
- `/health` - Health check endpoint
- WebSocket log endpoints

#### request_processor.py - Request Processing Core
- Implementation of three-tier response acquisition mechanism
- Streaming and non-streaming response handling
- Client disconnection detection
- Error handling and retry logic

#### queue_worker.py - Queue Worker
- Asynchronous request queue processing
- Concurrency control and resource management
- Request priority handling

### browser_utils/ - Browser Automation

#### page_controller.py - Page Controller
- Camoufox browser lifecycle management
- Page navigation and state monitoring
- Authentication file management

#### script_manager.py - Script Injection Management (v3.0)
- Playwright native network interception
- Tampermonkey script parsing and injection
- Model data synchronization

#### model_management.py - Model Management
- AI Studio model list acquisition
- Model switching and validation
- Excluded model processing

### config/ - Configuration Management

#### settings.py - Main Settings
- `.env` file loading
- Environment variable parsing
- Configuration validation and default values

#### constants.py - System Constants
- API endpoint constants
- Error code definitions
- System identifiers

### stream/ - Streaming Proxy Service

#### proxy_server.py - Proxy Server
- HTTP/HTTPS proxy implementation
- Request interception and modification
- Upstream proxy support

#### interceptors.py - Request Interceptors
- AI Studio request interception
- Response data parsing
- Streaming data processing

## Three-Tier Response Acquisition Mechanism

### Tier 1: Integrated Streaming Proxy (Stream Proxy)
- **Location**: `stream/` module
- **Port**: 3120 (configurable)
- **Advantages**: Best performance, direct request processing
- **Use Case**: Daily usage, production environment

### Tier 2: External Helper Service
- **Configuration**: Via `--helper` parameter or environment variables
- **Dependencies**: Requires valid authentication file
- **Use Case**: Backup solution, special environments

### Tier 3: Playwright Page Interaction
- **Location**: `browser_utils/` module
- **Method**: Browser automation operations
- **Advantages**: Full parameter support, ultimate fallback
- **Use Case**: Debug mode, precise parameter control

## Authentication System Architecture

### API Key Management
- **Storage**: `key.txt` file
- **Format**: One key per line
- **Validation**: Bearer Token and X-API-Key dual support
- **Management**: Web UI tiered permission viewing

### Browser Authentication
- **Files**: `auth_profiles/active/*.json`
- **Content**: Browser sessions and cookies
- **Updates**: Re-acquired through debug mode

## Configuration Management Architecture

### Configuration Priority
1. **Command-line parameters** (highest priority)
2. **Environment variables** (`.env` file)
3. **Default values** (defined in code)

### Configuration Categories
- **Service configuration**: Ports, proxies, logging, etc.
- **Feature configuration**: Script injection, authentication, timeouts, etc.
- **API configuration**: Default parameters, model settings, etc.

## Script Injection Architecture v3.0

### Working Mechanism
1. **Script Parsing**: Parse `MODELS_TO_INJECT` array from Tampermonkey scripts
2. **Network Interception**: Playwright intercepts `/api/models` requests
3. **Data Merging**: Merge injected models with original models
4. **Response Modification**: Return complete list including injected models
5. **Frontend Injection**: Simultaneously inject scripts to ensure display consistency

### Technical Advantages
- **100% Reliable**: Playwright native interception, no timing issues
- **Zero Maintenance**: Script updates take effect automatically
- **Fully Synchronized**: Frontend and backend use the same data source

## Development and Deployment

### Development Environment
- **Dependency Management**: Poetry
- **Type Checking**: Pyright
- **Code Formatting**: Black + isort
- **Testing Framework**: pytest

### Deployment Methods
- **Local Deployment**: Poetry virtual environment
- **Docker Deployment**: Multi-stage build, multi-architecture support
- **Configuration Management**: Unified `.env` file

## Performance Optimization

### Asynchronous Processing
- Comprehensive use of `async/await`
- Asynchronous queue request processing
- Concurrency control and resource management

### Caching Mechanism
- Model list caching
- Authentication status caching
- Configuration hot reload

### Resource Management
- Browser instance reuse
- Connection pool management
- Memory optimization

## Monitoring and Debugging

### Logging System
- Tiered log recording
- WebSocket real-time logging
- Error tracking and reporting

### Health Checks
- Component status monitoring
- Queue length monitoring
- Performance metrics collection

This detailed architecture documentation provides a comprehensive view of the system's design and implementation, supporting both current development and future enhancements.