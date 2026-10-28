# 🔨 Forge

> AI-Powered Coding Assistant Desktop Application (GUI like Antigravity & ChatGPT Codex), with Telegram Remote & Native Android Control.

```
Windows Desktop GUI App (.exe) ─┐
Terminal CLI (`forge chat`) ────┼─> Forge Runtime on your PC ─> Ollama (Default Local) + Project Tools
Telegram bot ───────────────────┤                               (Optional: OpenAI, Claude, Gemini)
Native Android App ─────────────┘
```

Your PC remains the **only machine** running the AI model, accessing the filesystem, running terminal commands, and managing Git. Telegram and the Android app act as remote controllers.

Repository: **[https://github.com/Hemant-Gujarati/Forge2](https://github.com/Hemant-Gujarati/Forge2)**

---

## 🎨 Antigravity & Codex Desktop GUI

When you launch `forge.exe` or type `forge`, Forge opens a **full native desktop window** with a modern dark-mode interface:

- **Split-Screen Workspace**:
  - **Left Pane (Agent & Chat)**: Real-time token streaming, tool call execution pills, collapsible thinking blocks, and quick prompt chips.
  - **Right Pane (Code & Diff Reviewer)**: Tabbed code viewer with syntax highlighting (Prism.js), side-by-side / inline diff review for proposed changes, and live terminal command logs.
- **Interactive File Explorer**: Click any file in your project directory to inspect it in the editor.
- **Visual Safety Approvals**: Modifying actions (`write_file`, `edit_file`, `delete_file`, `run_command`, `git_commit`) show an interactive diff banner with one-click **Approve** and **Reject** buttons.
- **Model Selector**: Switch between local Ollama models (`llama3.2`, `codellama`, `qwen2.5-coder`) and cloud providers (`gpt-4o`, `claude-3-7-sonnet`, `gemini-2.0-flash`) in one click.

---

## 📦 How to Get and Run Forge

### Option A: Standalone Windows App (`forge.exe`) — No Setup Required!
You do **not** need Python, Git, or pip installed.
1. Download **`forge.exe`** from [GitHub Releases](https://github.com/Hemant-Gujarati/Forge2/releases).
2. **Double-click `forge.exe`** to open the Desktop GUI immediately!
3. To compile `forge.exe` yourself:
   ```cmd
   build.bat
   ```

### Option B: From Source (Python 3.10+)
```bash
git clone https://github.com/Hemant-Gujarati/Forge2.git
cd Forge2
pip install -e .

# Launch Desktop GUI
forge

# Or launch terminal CLI mode
forge chat
```

---

## 📱 Remote Control via Telegram & Android

### 1. Telegram Remote (Direct Long Polling)
No public IP, port-forwarding, or ngrok required:
```bash
# Set your bot token from @BotFather
forge config --set-key telegram <YOUR_BOT_TOKEN>

# Start background server
forge serve --poll
```
Message your bot from Telegram on your phone:
- `/new Create a modern dashboard using HTML/CSS`
- `/approve <id>` or `/reject <id>`
- `/status` and `/tasks`

### 2. Native Android App (`android/`)
Native Kotlin + Jetpack Compose app in the [`android/`](file:///android/) folder:
- Open `android` in Android Studio and run on your device.
- Connect to your PC via local Wi-Fi or private VPN (Tailscale/WireGuard) to view logs, chat with Forge, and tap Approve/Reject on action cards.

---

## 🛡️ Safety & Approval Engine

Forge operates in safe mode by default:
- **Read-only actions** (`read_file`, `list_directory`, `find_files`, `search_text`, `git_status`, `git_diff`, `git_log`) execute immediately.
- **Modifying / destructive actions** require explicit human approval before running:
  - `write_file` (creating/overwriting files)
  - `edit_file` (modifying code)
  - `delete_file` (deleting files/directories)
  - `run_command` (shell execution)
  - `git_commit` (committing changes)

---

## 🧪 Testing & CI

Run all 34 automated unit and integration tests with pytest in one command:

```bash
pytest
```

Run code formatting and linting:

```bash
ruff check .
ruff format .
```

---

## 📄 License

MIT License.
