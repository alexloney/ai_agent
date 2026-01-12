# ai_agent

A self-hosted AI coding agent that automatically implements fixes for GitHub issues, inspired by GitHub Copilot.

## 🌟 Features

- **🧠 Intelligent Code Analysis**: Understands your codebase structure, patterns, and conventions
- **📋 Comprehensive Planning**: Creates detailed implementation plans with multi-step reasoning
- **🔧 Context-Aware Fixes**: Generates high-quality fixes that follow your coding standards
- **🧪 Automated Testing**: Validates changes in sandboxed Docker environment
- **🔄 Self-Healing**: Iteratively repairs code based on test feedback
- **📝 Professional PRs**: Creates detailed pull requests with clear explanations
- **🚧 WIP PR Workflow**: Creates PR early, updates during work, finalizes when complete
- **🔁 Review-Refactor Loop**: Automatically reviews and refactors code until quality standards met
- **📦 Multi-Language Support**: Extensible architecture supports multiple programming languages
- **✨ File Creation**: Can create new files as part of implementation

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

The agent follows a 6-phase process with iterative improvements:

1. **Analyze Codebase** - Understands your code patterns and conventions
2. **Plan Implementation** - Creates detailed plan identifying files to modify/create
3. **Create WIP PR** - Establishes PR early with "[WIP]" prefix for transparency
4. **Implement with Review Loop** - Applies changes, reviews code, refactors if needed (up to 3 iterations)
5. **Test & Validate** - Runs tests and repairs based on failures
6. **Finalize PR** - Removes WIP prefix and updates with comprehensive documentation

## 🔄 Improvements Over Basic Agents

This enhanced version (V16) includes:

- ✅ **Deep codebase analysis** before making changes
- ✅ **Multi-file context** awareness during implementation
- ✅ **Detailed implementation planning** with reasoning
- ✅ **WIP PR workflow** - create early, update during work, finalize at end
- ✅ **Review-refactor loop** - automatically reviews and improves code quality
- ✅ **Iterative commits** - commits progress during development
- ✅ **File creation support** - can create new files as needed
- ✅ **Language abstraction** - strategy pattern for multi-language support
- ✅ **Enhanced prompting** with comprehensive context
- ✅ **Professional PR generation** with detailed explanations
- ✅ **Better error handling** and edge case consideration

## 🛠️ Configuration

Key settings in `agent.py`:

```python
# Enable/disable sandboxed testing
ENABLE_SANDBOX = True

# Language strategy (supports multi-language projects)
LANGUAGE_STRATEGY = PythonStrategy()

# Review configuration
MAX_REVIEW_ITERATIONS = 3  # Maximum review-refactor cycles

# LLM configuration
llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)
```

### Language Support

The agent uses a strategy pattern for language-specific operations:

```python
from language_strategy import PythonStrategy, MultiLanguageStrategy

# For Python projects
LANGUAGE_STRATEGY = PythonStrategy()

# For multi-language projects (future)
# LANGUAGE_STRATEGY = MultiLanguageStrategy([
#     PythonStrategy(),
#     JavaScriptStrategy(),  # To be implemented
# ])
```

## 🔒 Security

- Tests run in isolated Docker containers
- Uses local Ollama LLM (no external API calls)
- GitHub access via standard `gh` CLI
- Always review generated code before merging

## 📊 Example Output

```
--- AI Agent V16 (Enhanced with WIP PR & Review Loop) ---

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
📌 Files to create (1): ['new_feature.py']

============================================================
CREATING WIP PULL REQUEST
============================================================
✅ Created WIP PR: https://github.com/owner/repo/pull/123

============================================================
PHASE 4: IMPLEMENTING CHANGES (with Review Loop)
============================================================
🔧 APPLYING FIX TO agent.py
✅ Successfully generated fix for agent.py
✨ CREATING NEW FILE: new_feature.py
✅ Successfully generated content for new_feature.py

--- 🔍 PERFORMING SELF-REVIEW (Iteration 1) ---
Self-Review Result: APPROVED - No concerns found
✅ Self-review passed!

============================================================
PHASE 5-6: TESTING AND FINALIZING PR
============================================================
✅ All tests passed!
✅ SUCCESS! Pull request finalized.
PR URL: https://github.com/owner/repo/pull/123
```

## 🏗️ Architecture

The agent now uses a modular architecture:

### Core Modules

- **`agent.py`** - Main orchestration logic and workflow
- **`language_strategy.py`** - Language-specific strategy pattern
  - `LanguageStrategy` - Abstract base class
  - `PythonStrategy` - Python implementation
  - `MultiLanguageStrategy` - Support for polyglot projects
- **`pr_manager.py`** - GitHub PR lifecycle management
  - WIP PR creation
  - Progressive updates
  - Final PR finalization

This architecture makes it easy to:
- Add support for new programming languages
- Customize PR workflows
- Extend functionality without modifying core logic

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

See LICENSE file for details.

## 🙏 Acknowledgments

Inspired by GitHub Copilot's approach to automated code generation and issue resolution.
