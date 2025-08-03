# AI Studio Proxy API - Claude Configuration

This file contains project-specific configurations and references to detailed rule documents.

## Project Information
- **Project**: AI Studio Proxy API
- **Owner**: Jason Zhang (new files)
- **Primary Language**: Python
- **Architecture**: Modular, following bacterial programming principles

## Rule Management System

All project rules are organized in the `.claude/rules/` directory:

### Core Programming Rules
- [Programming Rules](rules/programming-rules.md) - Bacterial programming principles and coding standards
- [File Structure Rules](rules/file-structure-rules.md) - Project organization and naming conventions

### Development Process Rules
- [Testing System Rules](rules/testing-system-rules.md) - Comprehensive testing protocols and standards
- [Memory System Rules](rules/memory-system-rules.md) - Knowledge capture and continuous improvement

### Project Details
- [Architecture](rules/project-details/architecture.md) - Detailed system architecture
- [Specifications](rules/project-details/specifications.md) - Complete project specifications
- [Implementation Guide](rules/project-details/implementation-guide.md) - Practical development guidance

## Key Project Configuration

### Environment Setup
- Virtual environment path: `./venv`
- Dependency management: Poetry
- Type checking: Pyright
- Configuration files: `.env` based

### Development Commands
- **Development Mode**: `python launch_camoufox.py --debug`
- **GUI Launcher**: `python gui_launcher.py`
- **Multi-Instance**: `python launch_camoufox.py --multi`
- **Testing**: `./test-runner.sh`

### Docker Deployment
- Configuration: `docker/.env`
- Deployment: `docker compose up -d`
- Updates: `bash docker/update.sh`

## Integration with Global Rules

This project follows the global rules defined in `~/.claude/CLAUDE.md` with these specific adaptations:

1. **Virtual Environment**: Using Poetry instead of venv for dependency management
2. **Testing**: Using project-specific test runner instead of generic scripts
3. **Configuration**: Using `.env` files for all configuration management
4. **Deployment**: Supporting both local Poetry and Docker deployment

## References
- [Main README](../README.md) - Project overview and quick start
- [Architecture Guide](../docs/architecture-guide.md) - High-level architecture
- [Documentation](../docs/) - Complete user documentation

This configuration file provides quick access to all project rules and key information while maintaining consistency with global development standards.