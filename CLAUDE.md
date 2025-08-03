# AI Studio Proxy API - Developer Guide

This file provides essential guidance for Claude Code when working with this repository.

## Quick Navigation

- [📚 Project Rules](#project-rules) - Essential coding and development standards
- [📁 Key Paths](#key-paths) - Important directories and files
- [🚀 Quick Start](#quick-start) - Getting up and running
- [🧪 Testing](#testing) - How to run and write tests
- [🐛 Debugging](#debugging) - Debugging tools and techniques
- [📦 Build & Deployment](#build--deployment) - Building and deploying the application

## Project Rules

This project follows specific rules for development and maintenance:

1. **[Programming Rules](.claude/rules/programming-rules.md)** - Bacterial programming principles and coding standards
2. **[File Structure Rules](.claude/rules/file-structure-rules.md)** - Project organization and naming conventions
3. **[Testing System Rules](.claude/rules/testing-system-rules.md)** - Testing principles and practices
4. **[Memory System Rules](.claude/rules/memory-system-rules.md)** - Knowledge capture and learning processes

## Key Paths

### Core Directories

- `api_utils/` - FastAPI routes and request processing
- `browser_utils/` - Browser automation and model management
- `config/` - Configuration files and constants
- `stream/` - Streaming proxy server implementation
- `multi_instance/` - Multi-account instance management
- `auth_profiles/` - Authentication files for AI Studio accounts
- `docs/` - Detailed documentation
- `test/` - Test files and test documentation

### Configuration

- `.env` - Main configuration file
- `.env.example` - Configuration template
- `config/` - Configuration modules

### Rules and Documentation

- `.claude/rules/` - All project rules and standards
- `.claude/rules/project-details/` - Detailed project specifications
- `docs/` - User guides and technical documentation

## Quick Start

### Environment Setup

1. Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
2. Install dependencies: `poetry install`
3. Copy and configure `.env` file: `cp .env.example .env`
4. Activate virtual environment: `poetry shell`

### Running the Application

- Launch with GUI: `poetry run python gui_launcher.py`
- Launch from command line: `poetry run python launch_camoufox.py`
- Run in multi-instance mode: `poetry run python launch_camoufox.py --multi`

## Testing

### Running Tests

- Run all tests: `poetry run pytest`
- Run specific test file: `poetry run pytest tests/test_file.py`
- Run tests with coverage: `poetry run pytest --cov=.`

### Test Organization

Tests are organized following our [Testing System Rules](.claude/rules/testing-system-rules.md):

- `test/functional/` - Functional tests
- `test/integration/` - Integration tests
- `test/pipeline/` - Pipeline tests
- `test/performance/` - Performance tests
- `test/docs/` - Test documentation

## Debugging

### Log Files

- Check logs in `logs/` directory
- Enable debug logging: Set `SERVER_LOG_LEVEL=DEBUG` in `.env`
- Enable trace logging: Set `TRACE_LOGS_ENABLED=true` in `.env`

### Debug Tools

- Monitor WebSocket logs: Connect to `/ws/logs` endpoint
- Debug scripts in `test/debug/`
- Follow [Debugging Rules](.claude/rules/testing-system-rules.md#isolated-debugging-principles) for systematic debugging

## Build & Deployment

### Docker Deployment

See `docker/README.md` for Docker deployment instructions.

### Dependency Management

- Update dependencies: `poetry update`
- Add new dependency: `poetry add package_name`
- Add dev dependency: `poetry add --group dev package_name`

### Project Memory

This project follows [Memory System Rules](.claude/rules/memory-system-rules.md) for capturing and organizing knowledge:

- New learnings are recorded in appropriate documentation
- Rule updates follow the established process
- Experience documentation is maintained in `.claude/knowledge/` (if exists)

---

*For detailed project architecture and implementation, see [Project Details](.claude/rules/project-details/)*