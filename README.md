# ai_agent

A self-hosted AI coding agent that automatically implements fixes for GitHub issues, inspired by GitHub Copilot.

## 🌟 Features

- **🧠 Intelligent Code Analysis**: Understands your codebase structure, patterns, and conventions
- **📋 Comprehensive Planning**: Creates detailed implementation plans with multi-step reasoning
- **🔧 Context-Aware Fixes**: Generates high-quality fixes that follow your coding standards
- **🧪 Automated Testing**: Validates changes in sandboxed Docker environment
- **🔄 Self-Healing**: Iteratively repairs code based on test feedback
- **📝 Professional PRs**: Creates detailed pull requests with clear explanations

## 🚀 Quick Start

1. **Install prerequisites**:
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen2.5-coder:32b-instruct
   
   # Install GitHub CLI
   brew install gh  # macOS
   # or: https://github.com/cli/cli#installation
   
   # Install Python dependencies
   pip install langchain-ollama gitpython
   ```

2. **Run the agent**:
   ```bash
   cd /path/to/your/repository
   python /path/to/agent.py
   ```

3. **Enter issue number** when prompted, and let the agent work its magic! ✨

## 📖 Documentation

- **[INSTALL.md](INSTALL.md)** - Complete installation guide with prerequisites
- **[USAGE.md](USAGE.md)** - Comprehensive usage guide with examples
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration examples for different projects

Quick links:
- Detailed feature descriptions
- Configuration options
- Advanced usage examples
- Troubleshooting guide
- Comparison with GitHub Copilot

## 🎯 How It Works

The agent follows a 6-phase process:

1. **Analyze Codebase** - Understands your code patterns and conventions
2. **Plan Implementation** - Creates detailed plan with reasoning
3. **Gather Context** - Reads all relevant files for comprehensive understanding
4. **Implement Fixes** - Applies changes following best practices
5. **Test & Validate** - Runs tests and repairs based on failures
6. **Create PR** - Commits and creates professional pull request

## 🔄 Improvements Over Basic Agents

This enhanced version includes:

- ✅ **Deep codebase analysis** before making changes
- ✅ **Multi-file context** awareness during implementation
- ✅ **Detailed implementation planning** with reasoning
- ✅ **Iterative repair loop** for test failures
- ✅ **Enhanced prompting** with comprehensive context
- ✅ **Professional PR generation** with detailed explanations
- ✅ **Better error handling** and edge case consideration

## 🛠️ Configuration

Key settings in `agent.py`:

```python
# Enable/disable sandboxed testing
ENABLE_SANDBOX = True

# Docker configuration for tests
DOCKER_IMAGE = "python:3.11-slim"
DOCKER_TEST_COMMAND = "pip install pytest -r requirements.txt -q && pytest"

# LLM configuration
llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)
```

## 🔒 Security

- Tests run in isolated Docker containers
- Uses local Ollama LLM (no external API calls)
- GitHub access via standard `gh` CLI
- Always review generated code before merging

## 📊 Example Output

```
--- AI Agent V15 (Copilot-Enhanced) ---

============================================================
PHASE 1: ANALYZING CODEBASE
============================================================
🔍 ANALYZING CODEBASE STRUCTURE
Codebase Analysis:
- Python 3.x codebase using langchain and GitPython
- Follows PEP 8 conventions with 4-space indentation
- Uses type hints and docstrings
- Error handling with try/except blocks
...

============================================================
PHASE 2: PLANNING IMPLEMENTATION
============================================================
📋 PLANNING CHANGES
Implementation Plan:
[Detailed reasoning about the issue and planned changes]

📌 Files to modify (2): ['agent.py', 'utils.py']

============================================================
PHASE 3-6: IMPLEMENTING, TESTING, AND CREATING PR
============================================================
...
✅ SUCCESS! Pull request created.
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

See LICENSE file for details.

## 🙏 Acknowledgments

Inspired by GitHub Copilot's approach to automated code generation and issue resolution.
