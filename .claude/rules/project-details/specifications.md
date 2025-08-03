# Project Specifications

## System Requirements

### Python Requirements
- **Version**: >=3.9, <4.0 (Recommended 3.10+ for best performance)
- **Dependency Management**: Poetry (modern Python dependency management tool)
- **Type Checking**: Pyright (optional, for development-time type checking and IDE support)

### Operating System Support
- **Windows**: Full support
- **macOS**: Full support
- **Linux**: Full support
- **Docker Deployment**: x86_64 and ARM64 architecture support

### Hardware Requirements
- **Memory**: Recommended 2GB+ available memory (for browser automation)
- **Network**: Stable internet connection for accessing Google AI Studio (proxy configuration supported)

## Core Features

### OpenAI Compatible API
- Support for `/v1/chat/completions` endpoint
- Full compatibility with OpenAI clients and third-party tools

### Multi-Instance Login Support
- Support for multiple AI Studio accounts logged in simultaneously
- Intelligent load balancing for concurrent processing and high availability

### Three-Tier Streaming Response Mechanism
- Integrated streaming proxy → External Helper service → Playwright page interaction
- Multiple layers of assurance for response delivery

### Intelligent Model Switching
- Dynamic model switching in AI Studio through the `model` field in API requests

### Complete Parameter Control
- Support for `temperature`, `max_output_tokens`, `top_p`, `stop`, `reasoning_effort` and all major parameters

### Anti-Fingerprinting
- Use of Camoufox browser to reduce the risk of being detected as an automation script

### Script Injection Function v3.0
- Use of Playwright native network interception
- Support for dynamic Tampermonkey script mounting
- 100% reliability

### Modern Web UI
- Built-in test interface
- Real-time chat support
- Status monitoring
- Tiered API key management

### Graphical Interface Launcher
- Feature-rich GUI launcher
- Simplified configuration and process management

### Flexible Authentication System
- Support for optional API key authentication
- Full compatibility with OpenAI standard Bearer token format

### Modular Architecture
- Clear module separation design
- Independent modules: api_utils/, browser_utils/, config/, etc.

### Unified Configuration Management
- Based on `.env` file unified configuration approach
- Support for environment variable overrides
- Docker compatibility

### Modern Development Tools
- Poetry dependency management + Pyright type checking
- Excellent development experience

## Multi-Instance Support (v4.0 Features)

### Core Features
- **Intelligent Load Balancing**: Automatically distribute requests to the least busy instance
- **Horizontal Scaling**: Support multiple authentication files, each corresponding to an independent browser instance
- **Fault Transfer**: Automatic switching to other available instances when a single instance fails
- **Instance Isolation**: Each instance has an independent locking mechanism to avoid global blocking
- **Real-time Monitoring**: Provides `/api/locks` and `/api/load-balancing` monitoring endpoints

### Performance Improvements
| Metric | Single Instance | Multi-Instance (3 accounts) |
|--------|-----------------|----------------------------|
| Concurrent Processing | 1 request/time | 3 requests/time |
| Fault Recovery | Service interruption | Automatic failover |
| Load Distribution | Global lock | Instance-level lock |
| Scalability | Limited | Horizontal scaling |

## Configuration Management

### Environment Variables
The project now supports configuration management through `.env` files to avoid hardcoding parameters.

### Key Configuration Options
- **Server Port**: Default 2048
- **Streaming Proxy Port**: Default 3120
- **Camoufox Ports**: Starting from 9222, incrementing for multi-instance
- **Authentication Files**: Path to auth session JSON files
- **API Keys**: Path to key.txt or inline configuration
- **Logging Level**: Control verbosity of logging output
- **Proxy Settings**: HTTP/HTTPS proxy configuration for external access

## API Endpoints

### Primary Endpoints
- **POST /v1/chat/completions**: Main chat completion endpoint
- **GET /v1/models**: List available models
- **GET /health**: Health check endpoint

### Management Endpoints
- **GET /api/locks**: View lock status
- **GET /api/load-balancing**: View load balancing statistics
- **GET /api/keys**: View API keys (with authentication)
- **POST /api/keys**: Add new API key (with authentication)
- **DELETE /api/keys/{key}**: Remove API key (with authentication)

### WebSocket Endpoints
- **WebSocket /logs**: Real-time log streaming

## Client Compatibility

### OpenAI Compatible Clients
- Full compatibility with OpenAI SDKs
- Support for third-party tools like Open WebUI
- Standard Bearer token authentication

### Configuration Example (Open WebUI)
1. Open Open WebUI
2. Go to "Settings" -> "Connections"
3. In the "Models" section, click "Add Model"
4. **Model Name**: Enter desired name, e.g., `aistudio-gemini-py`
5. **API Base URL**: Enter `http://127.0.0.1:2048/v1`
6. **API Key**: Leave empty or enter any character
7. Save settings and start chatting

## Security Considerations

### Authentication
- Optional API key authentication
- Support for both Bearer token and X-API-Key headers
- Key storage in `key.txt` file (gitignored)
- Web UI tiered access control

### Data Protection
- No storage of chat history on the server
- Client-managed conversation history
- Secure handling of authentication sessions
- Environment-based configuration management

### Network Security
- Support for HTTPS endpoints
- Proxy configuration for network access
- Certificate management for secure connections
- Isolation of browser instances

## Performance Characteristics

### Response Times
- **Streaming Proxy**: Fastest response times
- **Helper Service**: Moderate response times
- **Playwright Mode**: Slowest but most reliable

### Concurrent Handling
- **Single Instance**: Limited to one request at a time
- **Multi-Instance**: Parallel processing based on instance count
- **Queue Management**: Asynchronous request queuing

### Resource Usage
- **Memory**: Approximately 500MB-1GB per browser instance
- **CPU**: Moderate usage during active requests
- **Network**: Bandwidth proportional to response size

## Integration Capabilities

### Third-Party Tool Integration
- Open WebUI
- LibreChat
- Chatbot UIs supporting OpenAI API
- Custom applications using OpenAI SDKs

### Script Injection Support
- Tampermonkey script compatibility
- Dynamic model injection
- Custom functionality extension

### Proxy and Network Integration
- HTTP/HTTPS proxy support
- Corporate network compatibility
- Custom certificate support
- Load balancer compatibility

## Limitations and Constraints

### Technical Limitations
- Requires valid AI Studio authentication
- Browser automation resource intensive
- Network dependency for Google services
- Rate limiting by upstream services

### Functional Constraints
- No server-side chat history storage
- No UI-based history editing
- Client-managed conversation context
- Model availability dependent on AI Studio

## Future Development Directions

### Planned Improvements
- Cloud server deployment guides
- Authentication update process optimization
- Process robustness optimization
- Enhanced performance monitoring
- Extended multi-instance capabilities

This comprehensive specification document provides detailed information about the project's capabilities, requirements, and characteristics to guide development, deployment, and usage decisions.