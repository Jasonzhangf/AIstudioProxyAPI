# File Structure Rules

## Project Organization Standards

### Root Directory Structure
```
AIstudioProxyAPI/
├── .claude/                 # Claude configuration and rules
│   ├── rules/               # Rule management system
│   │   ├── programming-rules.md
│   │   ├── file-structure-rules.md
│   │   ├── testing-system-rules.md
│   │   ├── memory-system-rules.md
│   │   └── project-details/
│   └── CLAUDE.md            # Main configuration file
├── api_utils/               # FastAPI application core
├── browser_utils/           # Browser automation utilities
├── config/                  # Configuration management
├── docs/                   # User documentation
├── stream/                 # Streaming proxy service
├── multi_instance/         # Multi-instance support
├── auth_profiles/          # Authentication profiles
├── certs/                  # SSL certificates
├── docker/                 # Docker deployment files
├── errors_py/              # Error handling utilities
├── models/                 # Data models
├── logging_utils/          # Logging utilities
├── scripts/                # Utility scripts
├── test/                   # Test files (following testing system rules)
├── .env.example           # Environment configuration template
├── .gitignore             # Git ignore patterns
├── LICENSE                # Project license
├── README.md              # Project overview
├── pyproject.toml         # Poetry configuration
├── poetry.lock            # Poetry lock file
└── key.txt                # API keys (gitignored)
```

### Module Directory Standards
Each module directory should follow this pattern:
```
module_name/
├── __init__.py            # Module initialization
├── README.md              # Module documentation
├── main_component.py      # Primary module component
├── supporting_components.py
└── utils.py               # Utility functions for the module
```

## Test Directory Structure

### Standard Test Organization
Following the testing system rules, tests should be organized as:
```
test/
├── functional/            # Functional tests (tool usage, multi-turn conversations)
├── integration/           # Integration tests (end-to-end, vendor integrations)
├── pipeline/              # Pipeline tests (6-step standard workflow)
├── performance/           # Performance tests (debugging, parsing performance)
└── docs/                  # Test documentation summaries
```

### Test File Naming Conventions
- **Functional tests**: `test-[功能描述].js`
- **Integration tests**: `test-[集成点]-[功能].js`
- **Pipeline tests**: `test-step[N]-[功能描述].js`
- **Performance tests**: `perf-[性能指标]-[测试场景].js`
- **Debug tests**: `debug-[问题域].js`

## Configuration Paths

### Environment Configuration
- **Primary**: `.env` file in project root
- **Template**: `.env.example` for reference
- **Docker**: `docker/.env` for containerized deployment

### Authentication Files
- **Active profiles**: `auth_profiles/active/*.json`
- **Backup profiles**: `auth_profiles/backup/*.json`
- **Multi-instance**: `multi_instance/*.json`

### Certificate Files
- **Location**: `certs/` directory
- **Naming**: `[domain].[crt|key]` format
- **CA certificates**: `ca.crt` and `ca.key`

## Naming Conventions

### File Names
- Use lowercase with underscores for separation
- Use descriptive names that indicate purpose
- Avoid special characters except underscores and hyphens
- Use plural names for directories containing multiple items

### Directory Names
- Use lowercase with underscores
- Use descriptive, noun-based names
- Avoid abbreviations unless widely understood
- Group related functionality in appropriately named directories

## File Creation Compliance

### Required Files for New Modules
1. `__init__.py` - Module initialization
2. `README.md` - Module documentation
3. Primary implementation file
4. Appropriate test files in `test/` directory

### Documentation Requirements
- All new modules must have a README.md
- All public functions should have docstrings
- Complex logic should be explained in comments
- Configuration files should have examples

### Version Control
- All new files should be added to git
- Sensitive files should be added to `.gitignore`
- Configuration templates should be provided
- Documentation should be updated with new features

## Cross-Module References

### Import Standards
- Use absolute imports for cross-module references
- Use relative imports only within the same module
- Avoid circular imports
- Document external dependencies clearly

### Interface Files
- Each module should define a clear public interface
- Use `__all__` in `__init__.py` to specify public API
- Keep internal implementation details private
- Provide migration guides for breaking changes

These file structure rules ensure consistent organization, easy navigation, and maintainable code across the project while supporting the testing and documentation standards.