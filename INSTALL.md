# Installation Guide

## Prerequisites Installation

### 1. Install Ollama

**macOS/Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from [ollama.com](https://ollama.com/download)

### 2. Pull the LLM Model

```bash
ollama pull qwen2.5-coder:32b-instruct
```

**Alternative models** (if you have less RAM):
```bash
# For systems with less RAM (16GB)
ollama pull qwen2.5-coder:14b-instruct

# For systems with limited RAM (8GB)
ollama pull qwen2.5-coder:7b-instruct
```

### 3. Install GitHub CLI

**macOS:**
```bash
brew install gh
```

**Linux (Debian/Ubuntu):**
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

**Windows:**
```powershell
winget install --id GitHub.cli
```

**Authenticate GitHub CLI:**
```bash
gh auth login
```

### 4. Install Docker

**macOS:**
```bash
brew install --cask docker
# Or download Docker Desktop from docker.com
```

**Linux (Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

**Windows:**
Download Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)

### 5. Install Python Dependencies

```bash
cd /path/to/ai_agent
pip install -r requirements.txt
```

Or install manually:
```bash
pip install langchain-ollama gitpython langchain-core
```

## Verification

Verify all prerequisites are installed:

```bash
# Check Ollama
ollama --version

# Check if model is available
ollama list | grep qwen2.5-coder

# Check GitHub CLI
gh --version

# Check Docker
docker --version
docker ps

# Check Python packages
python -c "import langchain_ollama, git; print('✅ Python packages installed')"
```

## Starting Ollama Server

If Ollama isn't running, start it:

```bash
ollama serve
```

Keep this terminal open, or run it in the background.

## Common Issues

### "Connection refused" when running agent
**Solution:** Start Ollama server with `ollama serve`

### "gh: command not found"
**Solution:** Install GitHub CLI and add it to your PATH

### "Docker daemon not running"
**Solution:** Start Docker Desktop or run `sudo systemctl start docker`

### Model download is slow
**Solution:** Large models (32B) take time. Use a smaller model or wait for download to complete

### Permission denied for Docker
**Solution (Linux):** Add your user to docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

## System Requirements

### Minimum:
- 8GB RAM (for 7B model)
- 10GB free disk space
- Python 3.8+

### Recommended:
- 32GB RAM (for 32B model)
- 50GB free disk space
- Python 3.10+
- SSD storage

## Next Steps

After installation, see [USAGE.md](USAGE.md) for how to use the agent.
