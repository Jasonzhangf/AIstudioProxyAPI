# Implementation Guide

## Development Environment Setup

### Prerequisites
1. **Python**: Version 3.9-3.12 (3.10+ recommended)
2. **Poetry**: Modern Python dependency management tool
3. **Git**: For version control
4. **Code Editor**: With Python and Pyright support

### Installing Poetry
```bash
# macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Or use package managers
# macOS: brew install poetry
# Ubuntu/Debian: apt install python3-poetry
```

### Setting Up the Project
```bash
# Clone the repository
git clone https://github.com/CJackHwang/AIstudioProxyAPI.git
cd AIstudioProxyAPI

# Install dependencies
poetry install

# For development dependencies
poetry install --with dev

# Activate virtual environment
poetry shell

# Or run commands directly
poetry run python gui_launcher.py
```

## Project Structure Navigation

### Key Directories
- **api_utils/**: FastAPI application core
- **browser_utils/**: Browser automation utilities
- **config/**: Configuration management
- **stream/**: Streaming proxy service
- **docs/**: User documentation
- **test/**: Test files
- **docker/**: Docker deployment files

### Important Files
- **launch_camoufox.py**: Main entry point for command-line usage
- **gui_launcher.py**: Graphical interface launcher
- **server.py**: Alternative server entry point
- **pyproject.toml**: Poetry configuration
- **.env.example**: Configuration template

## Core Implementation Patterns

### Adding New API Endpoints
1. **Define route in `api_utils/routes.py`**
2. **Implement handler function**
3. **Add necessary dependencies in `api_utils/dependencies.py`**
4. **Update OpenAPI documentation**
5. **Add tests in `test/` directory**
6. **Update documentation in `docs/`**

### Extending Browser Functionality
1. **Add new operations in `browser_utils/operations.py`**
2. **Update page controller in `browser_utils/page_controller.py`**
3. **Add new selectors in `config/selectors.py`**
4. **Update model management in `browser_utils/model_management.py`**
5. **Add tests for new functionality**
6. **Update documentation**

### Configuration Management
1. **Add new settings in `config/settings.py`**
2. **Define defaults and validation**
3. **Add environment variable support**
4. **Update `.env.example`**
5. **Document new configuration options**

## Testing Implementation

### Writing New Tests
1. **Determine test category** (functional, integration, etc.)
2. **Create test file in appropriate `test/` subdirectory**
3. **Follow naming conventions** (`test-[功能描述].js`)
4. **Create corresponding documentation** (`.md` file)
5. **Implement test logic**
6. **Run and validate test**

### Running Tests
```bash
# Run all tests
./test-runner.sh

# Run specific category
./test-runner.sh --category functional

# Run specific test
./test-runner.sh test/functional/test-example.js

# List all tests
./test-runner.sh --list

# Search for tests
./test-runner.sh --search keyword
```

## Debugging Procedures

### Debugging New Features
1. **Before debugging, check existing documentation**
   - Review project CLAUDE.md and test directory documentation
   - Check existing test records in `test/` directory

2. **Create isolated test scripts for pipeline segments**
   - For complex workflows, create independent tests for each stage
   - Clearly define scope and expected results

3. **Document debugging process**
   - Create debugging records with naming: `test-[issue-keyword]-[YYYYMMDD]-[HHMM].md`
   - Include issue description, test method, findings, and solution

### Common Debugging Scenarios

#### Authentication Issues
1. **Check authentication files** in `auth_profiles/`
2. **Verify session validity** through manual browser login
3. **Update authentication** using debug mode
4. **Check configuration** in `.env` file

#### Browser Automation Problems
1. **Enable verbose logging**
2. **Check Camoufox installation**
3. **Verify selector definitions** in `config/selectors.py`
4. **Test page interactions** manually

#### API Response Issues
1. **Test three-tier response mechanism**
2. **Check streaming proxy** on port 3120
3. **Verify Helper service** configuration
4. **Test Playwright mode** directly

## Performance Optimization

### Identifying Performance Bottlenecks
1. **Profile request processing** in `api_utils/request_processor.py`
2. **Monitor browser automation** in `browser_utils/`
3. **Check streaming proxy** performance in `stream/`
4. **Analyze resource usage** during peak load

### Optimization Techniques
1. **Asynchronous processing** using `async/await`
2. **Caching** for frequently accessed data
3. **Connection pooling** for external services
4. **Resource cleanup** to prevent leaks
5. **Efficient data structures** for processing

## Deployment Procedures

### Local Deployment
1. **Install dependencies** using Poetry
2. **Configure environment** using `.env` file
3. **Prepare authentication** files
4. **Start service** using `launch_camoufox.py` or `gui_launcher.py`

### Docker Deployment
1. **Navigate to `docker/` directory**
2. **Prepare configuration** in `.env` file
3. **Use Docker Compose** to start services
4. **Monitor logs** for issues

### Multi-Instance Deployment
1. **Prepare multiple authentication files** in `multi_instance/`
2. **Start with `--multi` flag**
3. **Monitor instance status** via API endpoints
4. **Configure load balancing** as needed

## Common Implementation Tasks

### Adding New Models
1. **Update model definitions** in browser_utils
2. **Modify selector definitions** if needed
3. **Test model switching** functionality
4. **Update documentation** with new models

### Extending API Parameters
1. **Add parameter validation** in routes
2. **Implement parameter handling** in request processor
3. **Update browser operations** to use parameters
4. **Test parameter effects** thoroughly

### Adding New Configuration Options
1. **Define setting** in `config/settings.py`
2. **Add environment variable support**
3. **Provide default values** with validation
4. **Update `.env.example`**
5. **Document new options**

## Integration with External Systems

### Adding New Client Support
1. **Verify OpenAI API compatibility**
2. **Test authentication mechanisms**
3. **Validate parameter handling**
4. **Document client configuration**

### Extending Proxy Functionality
1. **Modify interceptors** in `stream/interceptors.py`
2. **Update proxy server** in `stream/proxy_server.py`
3. **Add new request handling** logic
4. **Test with real requests**

## Maintenance Procedures

### Regular Maintenance Tasks
1. **Update dependencies** using Poetry
2. **Run test suite** to verify functionality
3. **Check authentication files** for validity
4. **Review logs** for errors or warnings
5. **Update documentation** with changes

### Updating Dependencies
```bash
# Update all dependencies
poetry update

# Update specific dependency
poetry update package-name

# Show dependency tree
poetry show --tree

# Install updated dependencies
poetry install
```

### Version Management
1. **Follow semantic versioning** for releases
2. **Update version in `pyproject.toml`**
3. **Document breaking changes** in release notes
4. **Test backward compatibility** when possible

This implementation guide provides practical guidance for working with the project, covering setup, development, testing, debugging, deployment, and maintenance procedures. Following these guidelines ensures consistency with the project's architecture and development practices.