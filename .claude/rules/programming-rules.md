# Programming Rules

## Bacterial Programming Principles

### Small (小巧)
- Keep code concise and focused
- Eliminate unnecessary complexity
- Each function should have a single, clear purpose
- Minimize dependencies between components

### Modular (模块化)
- Organize code into self-contained modules
- Use functional grouping ("operons") for related functionality
- Design for easy combination and replacement of components
- Clear separation of concerns between modules

### Self-contained (自包含)
- Modules should be independently usable
- Minimize external context requirements
- Enable "horizontal gene transfer" - easy copying of useful components
- Reduce coupling between modules

## Code Design Standards

### Module Design
- Each module should have a single responsibility
- Modules should expose clear interfaces
- Internal implementation details should be hidden
- Prefer composition over inheritance

### Function Design
- Functions should be short and focused
- Each function should do one thing well
- Avoid side effects where possible
- Use pure functions when appropriate

### Error Handling
- Fail fast and provide clear error messages
- Handle errors at appropriate levels
- Don't use fallback mechanisms
- Validate inputs early

## Dependency Management

### External Dependencies
- All dependencies must be explicitly declared
- Use Poetry for Python dependency management
- Regularly update and audit dependencies
- Pin versions for reproducible builds

### Internal Dependencies
- Minimize circular dependencies
- Use clear import hierarchies
- Prefer explicit over implicit dependencies
- Document dependency relationships

## Type Safety

### Type Annotations
- Use type hints for all functions and variables
- Enable strict type checking with Pyright
- Regularly run type checking in development
- Treat type errors as build failures

### Interface Contracts
- Define clear interfaces between components
- Use dataclasses or Pydantic models for structured data
- Validate data at boundaries
- Document expected types in comments

## Code Quality

### Readability
- Write code for humans first, computers second
- Use descriptive variable and function names
- Include clear comments for complex logic
- Follow established naming conventions

### Maintainability
- Write automated tests for critical functionality
- Keep functions and classes small
- Avoid deeply nested code
- Refactor when complexity increases

## Performance

### Efficiency
- Optimize for common cases
- Avoid premature optimization
- Profile before optimizing
- Consider memory usage and allocation

### Resource Management
- Clean up resources explicitly
- Use context managers for resource handling
- Handle concurrency appropriately
- Monitor resource usage in production

## Security

### Input Validation
- Validate all external inputs
- Sanitize user-provided data
- Use parameterized queries for database access
- Implement proper authentication and authorization

### Configuration
- Never hardcode sensitive information
- Use environment variables for configuration
- Protect configuration files
- Rotate secrets regularly

## Testing Integration

### Testability
- Design code to be easily testable
- Use dependency injection for external services
- Separate business logic from I/O operations
- Provide test hooks where appropriate

### Code Coverage
- Aim for high test coverage
- Focus on critical paths and edge cases
- Use both unit and integration tests
- Regularly review coverage reports

These programming rules ensure code quality, maintainability, and alignment with the bacterial programming philosophy while meeting the specific needs of this project.