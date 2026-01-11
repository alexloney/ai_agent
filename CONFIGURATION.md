# Agent Configuration Examples

This file contains example configurations for different use cases.

## Python Projects

```python
# For Python projects with pytest
DOCKER_IMAGE = "python:3.11-slim"
DOCKER_TEST_COMMAND = "pip install -r requirements.txt -q && pytest"

# For Python projects with unittest
DOCKER_IMAGE = "python:3.11-slim"
DOCKER_TEST_COMMAND = "pip install -r requirements.txt -q && python -m unittest discover"

# For Python with specific dependencies
DOCKER_IMAGE = "python:3.11-slim"
DOCKER_TEST_COMMAND = "apt-get update && apt-get install -y build-essential && pip install -r requirements.txt -q && pytest"
```

## JavaScript/TypeScript Projects

```python
# For Node.js with Jest
DOCKER_IMAGE = "node:18-slim"
DOCKER_TEST_COMMAND = "npm install && npm test"

# For Node.js with specific test script
DOCKER_IMAGE = "node:18-slim"
DOCKER_TEST_COMMAND = "npm ci && npm run test:unit"

# For TypeScript projects
DOCKER_IMAGE = "node:18-slim"
DOCKER_TEST_COMMAND = "npm install && npm run build && npm test"
```

## Go Projects

```python
# For Go projects
DOCKER_IMAGE = "golang:1.21-alpine"
DOCKER_TEST_COMMAND = "go test ./..."

# For Go with module cache
DOCKER_IMAGE = "golang:1.21-alpine"
DOCKER_TEST_COMMAND = "go mod download && go test -v ./..."
```

## Rust Projects

```python
# For Rust projects
DOCKER_IMAGE = "rust:1.70-slim"
DOCKER_TEST_COMMAND = "cargo test"

# For Rust with specific features
DOCKER_IMAGE = "rust:1.70-slim"
DOCKER_TEST_COMMAND = "cargo test --all-features"
```

## Java Projects

```python
# For Maven projects
DOCKER_IMAGE = "maven:3.9-openjdk-17"
DOCKER_TEST_COMMAND = "mvn test"

# For Gradle projects
DOCKER_IMAGE = "gradle:8.2-jdk17"
DOCKER_TEST_COMMAND = "gradle test"
```

## LLM Model Configurations

```python
# For larger, more capable model (requires 64GB+ RAM)
llm = ChatOllama(
    model="qwen2.5-coder:72b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

# For medium model (requires 16GB+ RAM)
llm = ChatOllama(
    model="qwen2.5-coder:14b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

# For smaller, faster model (requires 8GB+ RAM)
llm = ChatOllama(
    model="qwen2.5-coder:7b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

# For creative/experimental fixes (higher temperature)
llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.3,  # More creative
    base_url="http://localhost:11434"
)

# For deterministic fixes (lower temperature)
llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.0,  # More deterministic
    base_url="http://localhost:11434"
)
```

## Alternative Models

```python
# Using CodeLlama
llm = ChatOllama(
    model="codellama:34b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

# Using DeepSeek Coder
llm = ChatOllama(
    model="deepseek-coder:33b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

# Using Mistral
llm = ChatOllama(
    model="mistral:7b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)
```

## Timeout Configurations

```python
# For fast test suites (< 1 minute)
DOCKER_TIMEOUT = 60

# For normal test suites (< 5 minutes)
DOCKER_TIMEOUT = 300

# For slow test suites (< 15 minutes)
DOCKER_TIMEOUT = 900

# For very slow test suites (< 30 minutes)
DOCKER_TIMEOUT = 1800
```

## Disabling Features

```python
# Skip sandboxed testing (faster but no validation)
ENABLE_SANDBOX = False

# Limit output for token management
MAX_TEST_OUTPUT_LENGTH = 2000  # Smaller output
MAX_TEST_OUTPUT_LENGTH = 8000  # Larger output for more context
```

## Multi-Language Projects

```python
# For projects with multiple languages, use a base image with multiple tools
DOCKER_IMAGE = "ubuntu:22.04"
DOCKER_TEST_COMMAND = """
apt-get update && \
apt-get install -y python3 python3-pip nodejs npm && \
pip3 install -r requirements.txt && \
npm install && \
python3 -m pytest && \
npm test
"""
```

## Remote Ollama Server

```python
# If running Ollama on a different machine
llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://192.168.1.100:11434"  # Remote server
)
```

## How to Apply Configuration

1. Open `agent.py`
2. Find the configuration section at the top (after imports)
3. Modify the values according to your needs
4. Save the file
5. Run the agent

Example:
```python
# --- CONFIGURATION ---
REPO_PATH = os.getcwd()

# SANDBOX CONFIGURATION
ENABLE_SANDBOX = True
DOCKER_IMAGE = "python:3.11-slim"  # Change this
DOCKER_TEST_COMMAND = "pip install pytest -r requirements.txt -q && pytest"  # And this

# OUTPUT CONFIGURATION
MAX_TEST_OUTPUT_LENGTH = 4000
DOCKER_TIMEOUT = 300

# LLM CONFIGURATION - Change this too
llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)
```
