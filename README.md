# 🔨 Forge CLI

> AI-Powered Agentic Coding Assistant CLI with Multi-Provider Support & Remote Access.

Forge is a terminal-based agentic coding assistant inspired by Antigravity and Codex. It works directly on your filesystem to inspect, edit, create, and manage code, run commands, and execute tasks autonomously — powered by online AI models (OpenAI, Anthropic Claude, Google Gemini) or 100% offline local LLMs via Ollama.

Forge also supports remote control via **Telegram** (and WhatsApp), letting you send tasks from your phone and have Forge execute them on your machine in the background.

---

## ✨ Features

- 🧠 **Multi-Provider Support**:
  - **Local LLMs**: Ollama (`llama3.2`, `codellama`, `deepseek-coder`, `qwen2.5-coder`, etc.)
  - **OpenAI**: `gpt-4o`, `o3-mini`, `gpt-4.5`, etc.
  - **OpenAI-Compatible**: Groq, Together AI, OpenRouter, vLLM, LM Studio
  - **Anthropic Claude**: `claude-3-7-sonnet`, `claude-3-5-sonnet`, etc.
  - **Google Gemini**: `gemini-2.0-flash`, `gemini-2.5-pro`, etc.
- ⚡ **Autonomous Agentic Loop**:
  - The model inspects the codebase, reasons, uses tools, checks results, and fixes its own mistakes automatically.
- 🛠️ **12 Built-in Tools**:
  - `read_file` - Read files with size guards
  - `write_file` - Create or overwrite files (auto-creates directories)
  - `edit_file` - Targeted exact search-and-replace
  - `delete_file` - Safely remove files or empty folders
  - `list_directory` - Tree view of files and folder sizes
  - `find_files` - Recursive glob file finder
  - `search_text` - Fast regex/text grep across the project
  - `run_command` - Shell command execution with stdout/stderr capture
  - `git_status` - Working directory status
  - `git_diff` - Staged and unstaged changes
  - `git_commit` - Stage and commit
  - `git_log` - Commit history
- 📱 **Remote Access via Telegram & WhatsApp**:
  - Control Forge from your phone
  - Tasks run as background jobs on your PC
  - Sends back execution results and code changes
- 💬 **Interactive Terminal UI**:
  - Rich markdown rendering and syntax highlighting
  - Input history and tab navigation
  - Quick slash commands (`/help`, `/model`, `/provider`, `/save`, `/load`, `/cd`, `/config`)

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/your-username/forge-cli.git
cd forge-cli
pip install -e .
```

Or run directly without installation:
```bash
python -m forge
```

### Basic Usage

```bash
# Start interactive session with default provider (Ollama)
forge

# Chat with a specific provider and model
forge chat -p openai -m gpt-4o
forge chat -p anthropic -m claude-3-7-sonnet
forge chat -p gemini -m gemini-2.0-flash
forge chat -p ollama -m qwen2.5-coder:7b

# List available models
forge models -p ollama
forge models -p openai

# Manage config
forge config --set-key openai sk-...
forge config --set-key anthropic sk-ant-...
forge config --set-key gemini AIza...
forge config --set-provider ollama
forge config --show
```

---

## 📱 Remote Control via Telegram

You can message Forge from your phone on Telegram to run tasks on your computer:

1. **Create a bot on Telegram**:
   - Message `@BotFather` on Telegram
   - Send `/newbot` and follow instructions to get your `bot_token`

2. **Configure Forge**:
   ```bash
   forge config --set-key telegram <YOUR_BOT_TOKEN>
   ```
   Or edit `~/.forge/config.yaml`:
   ```yaml
   server:
     telegram:
       bot_token: "YOUR_BOT_TOKEN"
       allowed_chat_ids: [123456789] # Optional: restrict to your Telegram user ID
   ```

3. **Start the server**:
   ```bash
   forge serve --port 5000
   ```

4. **Expose with a tunnel (ngrok)**:
   ```bash
   ngrok http 5000
   ```

5. **Register the webhook**:
   ```bash
   forge serve --setup-telegram https://<your-ngrok-subdomain>.ngrok-free.app
   ```

Now message your bot on Telegram:
> "Create a python script that fetches the latest top Hacker News stories and saves them to a json file"

Forge will execute the task on your PC and text you the result!

---

## 📂 Configuration

Configuration is stored at `~/.forge/config.yaml`:

```yaml
default_provider: ollama

providers:
  ollama:
    base_url: "http://localhost:11434"
    default_model: "llama3.2"
  openai:
    api_key: "sk-..."
    base_url: "https://api.openai.com/v1"
    default_model: "gpt-4o"
  anthropic:
    api_key: "sk-ant-..."
    base_url: "https://api.anthropic.com"
    default_model: "claude-sonnet-4-20250514"
  gemini:
    api_key: "AIza..."
    base_url: "https://generativelanguage.googleapis.com/v1beta"
    default_model: "gemini-2.0-flash"
```

---

## 📄 License

MIT License.
