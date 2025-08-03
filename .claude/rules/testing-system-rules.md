# Testing System Rules

## Core Testing Principles

### Four Fundamental Principles
1. **Script-based Testing**: All tests must be executed through scripts, manual testing is prohibited
2. **Descriptive Naming**: Each test file name must clearly express its purpose in one sentence
3. **Paired Documentation**: Each test file (.js) must have a corresponding documentation file (.md)
4. **Prior Art Check**: Before creating new tests, check existing tests in the test/ directory

## Test Organization Structure

### Directory Structure
```
test/
├── functional/     # Functional tests (tool usage, multi-turn conversations)
├── integration/    # Integration tests (end-to-end, vendor integrations)
├── pipeline/       # Pipeline tests (6-step standard workflow)
├── performance/    # Performance tests (debugging, parsing performance)
└── docs/          # Test documentation summaries
```

### Category Descriptions
- **Functional**: Tests for specific features and functionalities
- **Integration**: End-to-end tests covering complete workflows
- **Pipeline**: Tests for the 6-step standard processing pipeline
- **Performance**: Tests focused on performance metrics and optimization
- **Docs**: Summary documentation of test results and findings

## Test Naming Conventions

### File Naming
- **Test files**: `test-[one-sentence-description].js`
- **Documentation files**: `test-[one-sentence-description].md`
- **Log files**: `/tmp/test-[test-name]-[timestamp].log`

### Specialized Naming Patterns
- **Pipeline step tests**: `test-step[N]-[功能描述].js`
- **Component tests**: `test-[component-name]-[functionality].js`
- **Debug tests**: `debug-[issue-domain].js`
- **Performance tests**: `perf-[metric]-[scenario].js`

## Test Execution Standards

### Unified Test Runner
- **Primary tool**: `./test-runner.sh`
- **List all tests**: `./test-runner.sh --list`
- **Search tests**: `./test-runner.sh --search <keyword>`
- **Run by category**: `./test-runner.sh --category <category>`
- **Run single test**: `./test-runner.sh <test-file-path>`

### Test Execution Requirements
- All tests must run in isolated environments
- Tests should clean up after themselves
- Test results should be deterministic
- Failed tests should provide clear error messages

## Test Documentation Standards

### Required Documentation Elements
Each test documentation file (.md) must include:
1. **Test Case**: One-sentence description of test purpose
2. **Test Objective**: Specific issue or functionality being verified
3. **Recent Execution Record**: Date, status, duration, log file path
4. **Execution History**: Multiple execution records maintained
5. **Related Files**: Paths to test script and log files

### Documentation Updates
- Update documentation after every test execution
- Include both successful and failed test results
- Add analysis and insights from test runs
- Link to related issues or pull requests

## Test File Organization Rules

### Location Standards
- All test scripts must be in the project root `test/` directory
- Tests must be categorized into appropriate subdirectories
- Related tests should be grouped together
- Avoid creating duplicate test functionality

### Content Standards
- Test files should be self-contained
- Include setup and teardown procedures
- Use clear, descriptive variable names
- Comment complex test logic
- Follow project coding standards

## Isolated Debugging Principles

### Pipeline Segmentation
- For long processing pipelines, create independent test scripts for each stage
- Clearly define the scope and expected results for each test script
- Identify which specific stage has issues
- Map scripts to specific problem verification

### Debug Record Standards
- **File naming**: `test-[issue-keyword]-[YYYYMMDD]-[HHMM].md`
- **Required content**: Issue description, test method, findings, solution
- **Update mechanism**: Read existing records before creating new ones
- **Linking**: Connect related issues and test records

## Integration with Development Workflow

### Pre-commit Requirements
- Run relevant tests before committing changes
- Ensure all tests pass in the local environment
- Update test documentation with results
- Add new tests for new functionality

### Continuous Integration
- Automated test execution on pull requests
- Test result reporting in CI environment
- Performance regression detection
- Test coverage reporting

## Performance Testing

### Performance Test Categories
- **Load testing**: Concurrent request handling
- **Stress testing**: System behavior under extreme conditions
- **Soak testing**: Long-term stability verification
- **Scalability testing**: Performance with increasing load

### Performance Metrics
- Response time measurements
- Throughput rates
- Resource utilization
- Error rates under load

## Test Quality Assurance

### Code Review Requirements
- Test code should be reviewed like production code
- Verify test coverage is adequate
- Check for test flakiness
- Ensure tests are maintainable

### Test Maintenance
- Regular review and update of test suites
- Removal of obsolete tests
- Refactoring of complex tests
- Keeping test data current

These testing system rules ensure comprehensive, maintainable, and reliable testing practices that support the project's quality goals while integrating with the debugging and development workflows.