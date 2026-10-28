# 🔨 Forge

> AI-Powered Coding Assistant with Three Control Interfaces: CLI, Telegram, and Native Android.

```
Windows/Linux CLI ─┐
Telegram bot ─────┼─> Forge Runtime on your PC ─> Ollama (Local) / Online LLMs + Tools
Native Android ───┘
```

Your PC remains the **only machine** that runs the AI model, reads files, edits code, executes terminal commands, and manages Git. Telegram and the Native Android app act as remote controllers.

Repository: **[https://github.com/Hemant-Gujarati/Forge2](https://github.com/Hemant-Gujarati/Forge2)**

---

## 🌟 Architecture & Highlights

| Area | Choice | Cost |
|------|--------|------|
| **Desktop Core** | Python 3.11+ | Free |
| **Local AI Engine** | Ollama (`llama3.2`, `codellama`, `deepseek-coder`, `qwen2.5-coder`) | Free |
| **Online AI (Optional)** | OpenAI, Anthropic Claude, Google Gemini, Groq, OpenRouter | Optional API key |
| **CLI Interface** | Rich terminal UI + `prompt-toolkit` | Free |
| **Telegram Remote** | Telegram Bot API with Long Polling via `httpx` (no ngrok required) | Free |
| **Android App** | Native Kotlin + Jetpack Compose (`android/`) | Free |
| **Persistence** | SQLite (`~/.forge/forge.db`) for tasks, approvals, and sessions | Free |
| **Config** | Human-readable YAML (`~/.forge/config.yaml`) | Free |
| **Safety Engine** | Controlled approval system with pending, approved, rejected, and expired states | Free |
| **Source Control** | Git + GitHub Actions CI | Free |

---

## 🛡️ Safety & Approval System (Phase 2 & 3)

By default, Forge operates in safe mode:
- **Read-only actions** (`read_file`, `list_directory`, `find_files`, `search_text`, `git_status`, `git_diff`, `git_log`) execute immediately.
- **Destructive / modifying actions** require explicit human approval before running:
  - `write_file` (creating/overwriting files)
  - `edit_file` (modifying code)
  - `delete_file` (deleting files/directories)
  - `run_command` (shell execution)
  - `git_commit` (committing changes)

### How Approvals Work:
1. When the agent attempts a modifying action, a pending approval record is created in SQLite.
2. The user is prompted in their active interface:
   - **CLI**: Interactive `[y/N]` prompt
   - **Telegram**: Notification with `/approve <id>` and `/reject <id>` commands
   - **Android**: Interactive card in the Approvals tab with "Approve" and "Reject" buttons
3. Once approved, the agent continues its autonomous loop: edit -> test -> report.

---

## 📱 Three Ways to Control Forge

### 1. Windows / Linux Terminal CLI
```bash
# Clone & install
git clone https://github.com/Hemant-Gujarati/Forge2.git
cd Forge2
pip install -e .

# Launch interactive coding session (Ollama default)
forge

# Or use specific models
forge chat -p ollama -m llama3.2
forge chat -p openai -m gpt-4o
forge chat -p anthropic -m claude-3-7-sonnet
forge chat -p gemini -m gemini-2.0-flash

# View config & models
forge config --show
forge models -p ollama
```

### 2. Telegram Remote Control (Direct Long Polling)
No public IP, port-forwarding, or ngrok required:

1. Create a bot with `@BotFather` on Telegram to receive your `bot_token`.
2. Configure token and your chat ID:
   ```bash
   forge config --set-key telegram <YOUR_BOT_TOKEN>
   ```
3. Start the server in long-polling mode:
   ```bash
   forge serve --poll
   ```
4. Commands supported in Telegram:
   - `/help` - Display available commands
   - `/new <task>` - Start a new autonomous background coding task
   - `/tasks` - View recent tasks and their statuses
   - `/status` - Check current PC runtime and working directory
   - `/cancel <task_id>` - Abort an ongoing background task
   - `/approve <id>` - Approve a pending file edit, command, or commit
   - `/reject <id>` - Reject a pending action

### 3. Native Android App (`android/`)
Located in the [`android/`](file:///android/) directory:
- Built with **Kotlin + Jetpack Compose + Material 3**.
- Direct connection over private Wi-Fi / VPN (Tailscale, WireGuard) to your desktop's Forge REST API.
- **Screens**:
  1. **Pairing**: Connect via desktop IP:port and secure 6-digit or UUID pairing token.
  2. **Chat / Tasks**: Send coding prompts and receive real-time updates.
  3. **Task Detail**: View task execution progress, full stdout/stderr, and tool logs.
  4. **Approvals Screen**: View pending write/command/commit requests with one-tap Approve/Reject.
  5. **Recent Tasks**: History of all tasks stored in desktop SQLite.
  6. **Settings**: Connection status, token management, and desktop health.

---

## 🌐 Desktop REST API Endpoints (Phase 5)

The Forge server exposes a secure authenticated API for Android and remote controllers:

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/health` | Health check & provider status | None |
| `POST` | `/v1/pair` | Generate or verify pairing token | None / Pairing Token |
| `POST` | `/v1/tasks` | Submit a new background task | Bearer Token |
| `GET` | `/v1/tasks` | List recent tasks | Bearer Token |
| `GET` | `/v1/tasks/{id}` | Get task details, status, and logs | Bearer Token |
| `POST` | `/v1/tasks/{id}/cancel` | Cancel a running task | Bearer Token |
| `GET` | `/v1/approvals` | List pending approvals | Bearer Token |
| `POST` | `/v1/approvals/{id}/approve` | Approve a pending action | Bearer Token |
| `POST` | `/v1/approvals/{id}/reject` | Reject a pending action | Bearer Token |

---

## 🧪 Testing & CI

Run all 29 unit and integration tests with pytest in one command:

```bash
pytest
```

Run code formatting and linting:

```bash
ruff check .
ruff format .
```

GitHub Actions automatically runs tests on every push to `main`:
[`.github/workflows/test.yml`](file:///.github/workflows/test.yml)

---

## 📄 License

MIT License.
