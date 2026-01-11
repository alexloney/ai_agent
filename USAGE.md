# AI Agent Usage Guide

## Overview

This AI agent is designed to automatically implement fixes for GitHub issues, similar to GitHub Copilot. It analyzes your codebase, understands the context, and generates comprehensive solutions.

## Key Features

### 1. **Comprehensive Codebase Analysis**
The agent starts by analyzing your repository to understand:
- Programming languages and frameworks used
- Code style and conventions (indentation, naming, etc.)
- Common patterns (error handling, imports, class structure)
- Testing approaches
- Documentation style
- Project structure and organization

### 2. **Deep Issue Understanding**
Instead of just reading the issue, the agent:
- Analyzes the root cause or requirement
- Identifies which files need modification and why
- Plans the logical sequence of changes
- Considers edge cases and side effects
- Determines if tests need updates
- Identifies related files (configs, docs) for updates

### 3. **Context-Aware Implementation**
When implementing fixes, the agent:
- Follows your established codebase conventions
- Considers relationships between files
- Provides comprehensive error handling
- Adds meaningful comments where valuable
- Maintains code maintainability and best practices

### 4. **Iterative Testing & Repair**
The agent includes a smart repair loop that:
- Runs tests in a sandboxed environment
- Analyzes test failures intelligently
- Applies targeted fixes based on error analysis
- Iterates up to 3 times to achieve passing tests

### 5. **Professional PR Generation**
Creates detailed pull requests with:
- Clear commit messages following conventional commits
- Descriptive PR titles
- Comprehensive PR descriptions explaining:
  - What problem is solved
  - How it's solved
  - Key changes made
  - Important considerations or trade-offs

## Prerequisites

1. **GitHub CLI (`gh`)**: For fetching issues and creating PRs
   ```bash
   # Install on macOS
   brew install gh
   
   # Install on Linux
   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
   sudo apt update
   sudo apt install gh
   ```

2. **Ollama with Qwen2.5-Coder**: The LLM for code analysis and generation
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull the model
   ollama pull qwen2.5-coder:32b-instruct
   
   # Start Ollama server (if not already running)
   ollama serve
   ```

3. **Docker**: For sandboxed test execution
   ```bash
   # Install Docker
   # See: https://docs.docker.com/get-docker/
   ```

4. **Python Dependencies**:
   ```bash
   pip install langchain-ollama gitpython
   ```

5. **Git Repository**: The agent must be run from within a git repository

## Usage

### Basic Usage

1. Navigate to your repository:
   ```bash
   cd /path/to/your/repository
   ```

2. Run the agent:
   ```bash
   python /path/to/agent.py
   ```

3. Enter the GitHub issue number when prompted:
   ```
   Enter Issue Number to fix: 42
   ```

4. The agent will:
   - Analyze your codebase
   - Plan the implementation
   - Apply fixes
   - Run tests and repair if needed
   - Create a branch (e.g., `fix/issue-42`)
   - Commit changes
   - Push to GitHub
   - Create a pull request

### Configuration Options

You can modify these settings in `agent.py`:

```python
# Repository path (default: current working directory)
REPO_PATH = os.getcwd()

# Enable/disable sandboxed testing
ENABLE_SANDBOX = True

# Docker image for testing
DOCKER_IMAGE = "python:3.11-slim"

# Docker test command
DOCKER_TEST_COMMAND = "pip install pytest -r requirements.txt -q && pytest"

# Maximum test output length (to avoid overwhelming the LLM)
MAX_TEST_OUTPUT_LENGTH = 4000

# Docker timeout in seconds
DOCKER_TIMEOUT = 300

# LLM configuration
llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)
```

## How It Works (6-Phase Process)

### Phase 1: Analyzing Codebase
- Scans repository files
- Reads sample files to understand patterns
- Generates codebase analysis report

### Phase 2: Planning Implementation
- Reads file previews for context
- Creates detailed implementation plan
- Identifies specific files to modify
- Provides reasoning for each change

### Phase 3: Gathering Context
- Reads all target files completely
- Prepares related file context
- Builds comprehensive understanding

### Phase 4: Implementing Fixes
- Applies fixes with full context
- Follows codebase conventions
- Considers related files
- Maintains code quality

### Phase 5: Testing and Validation
- Runs tests in Docker sandbox
- Analyzes failures intelligently
- Applies targeted repairs (up to 3 iterations)
- Ensures tests pass before proceeding

### Phase 6: Committing and Creating PR
- Commits changes with meaningful message
- Pushes to feature branch
- Creates detailed pull request
- Includes implementation details

## Examples

### Example 1: Bug Fix
```
Issue #15: "Fix null pointer exception in user authentication"

The agent will:
1. Analyze the codebase to understand authentication patterns
2. Identify files involved in user authentication
3. Plan a fix that adds proper null checks
4. Implement the fix following existing patterns
5. Ensure tests pass
6. Create PR with detailed explanation
```

### Example 2: Feature Addition
```
Issue #23: "Add support for exporting data to CSV format"

The agent will:
1. Understand the current export functionality
2. Identify where CSV export should be added
3. Plan implementation including tests
4. Add CSV export feature
5. Update any related documentation
6. Create comprehensive PR
```

## Tips for Best Results

1. **Write Clear Issues**: The better the issue description, the better the fix
   - Describe the problem clearly
   - Include expected vs actual behavior
   - Provide relevant context

2. **Maintain Tests**: Having a good test suite helps the agent validate fixes
   - The agent can run tests and self-correct
   - Failed tests guide the repair process

3. **Consistent Codebase**: Well-structured code with consistent patterns
   - Agent learns from existing patterns
   - More consistent = better fixes

4. **Review PRs**: Always review the generated PR before merging
   - Agent is powerful but not perfect
   - Human review ensures quality

## Troubleshooting

### "gh command not found"
Install GitHub CLI and authenticate:
```bash
gh auth login
```

### "Docker executable not found"
Install Docker and ensure it's running:
```bash
docker --version
docker ps
```

### "Connection refused" (Ollama)
Start the Ollama server:
```bash
ollama serve
```

### Tests timing out
Increase `DOCKER_TIMEOUT` in the configuration or disable sandboxing:
```python
ENABLE_SANDBOX = False  # Skip testing
```

### Poor quality fixes
Try:
- Writing more detailed issue descriptions
- Adding more context to the issue
- Ensuring your codebase has clear patterns
- Using a larger/better model if available

## Advanced Configuration

### Using Different Models

You can use different Ollama models:

```python
# Smaller, faster model
llm = ChatOllama(model="codellama:13b", temperature=0.1)

# Larger, more capable model
llm = ChatOllama(model="qwen2.5-coder:72b-instruct", temperature=0.1)
```

### Custom Test Commands

Adapt the test command for your project:

```python
# For JavaScript projects
DOCKER_IMAGE = "node:18-slim"
DOCKER_TEST_COMMAND = "npm install && npm test"

# For Go projects
DOCKER_IMAGE = "golang:1.21-alpine"
DOCKER_TEST_COMMAND = "go test ./..."

# For Rust projects
DOCKER_IMAGE = "rust:1.70-slim"
DOCKER_TEST_COMMAND = "cargo test"
```

### Disabling Sandboxing

If Docker is not available or desired:

```python
ENABLE_SANDBOX = False
```

Note: Without sandboxing, the agent won't validate fixes before creating the PR.

## Comparison with GitHub Copilot

### Similarities
- Understands context and codebase patterns
- Generates comprehensive solutions
- Creates detailed PRs
- Iterates based on test feedback

### Differences
- Self-hosted (runs locally with Ollama)
- Open source and customizable
- Works with any git repository
- Can be tuned for specific codebases
- Requires local LLM setup

## Security Considerations

1. **Code Execution**: Tests run in Docker containers (sandboxed)
2. **API Keys**: Uses local Ollama (no external API calls for LLM)
3. **GitHub Access**: Uses `gh` CLI with your credentials
4. **Review Required**: Always review generated code before merging

## Future Enhancements

Potential improvements:
- [ ] Support for multiple LLM backends (OpenAI, Anthropic, etc.)
- [ ] Interactive mode for approving changes
- [ ] Support for multi-file refactoring
- [ ] Automatic documentation generation
- [ ] Integration with CI/CD pipelines
- [ ] Support for creating new test files
- [ ] Code review suggestions on existing PRs

## License

See repository LICENSE file.

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues or questions:
1. Check this documentation
2. Review existing GitHub issues
3. Create a new issue with details
