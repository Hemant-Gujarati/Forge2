/* Forge Desktop - Antigravity / Codex Reactive Client */

let currentWorkspace = "";
let currentActiveApprovalId = null;
let isStreaming = false;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initSettingsModal();
  loadWorkspace();
  loadModels();
  checkPendingApprovals();
  setInterval(checkPendingApprovals, 3000);

  // Send button & enter key
  document.getElementById("btn-send").addEventListener("click", sendPrompt);
  document.getElementById("prompt-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  });

  // Approval banner buttons
  document.getElementById("btn-banner-approve").addEventListener("click", () => {
    if (currentActiveApprovalId) handleApproval(currentActiveApprovalId, "approve");
  });
  document.getElementById("btn-banner-reject").addEventListener("click", () => {
    if (currentActiveApprovalId) handleApproval(currentActiveApprovalId, "reject");
  });
});

/* Tabs Switching */
function initTabs() {
  // Activity bar tabs (left)
  document.querySelectorAll(".act-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".act-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.tab;

      if (target === "explorer") {
        switchInspectorPane("explorer-pane");
      } else if (target === "approvals") {
        switchInspectorPane("diff-pane");
      } else if (target === "terminal") {
        switchInspectorPane("terminal-pane");
      }
    });
  });

  // Inspector tabs (right pane)
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      switchInspectorPane(btn.dataset.pane);
    });
  });
}

function switchInspectorPane(paneId) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.pane === paneId);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === paneId);
  });
}

/* Load Workspace & Files */
async function loadWorkspace() {
  try {
    const res = await fetch("/api/workspace");
    const data = await res.json();
    currentWorkspace = data.cwd || "";
    document.getElementById("workspace-path").textContent = currentWorkspace.split(/[\\/]/).pop() || currentWorkspace;
    document.getElementById("workspace-path").title = currentWorkspace;

    // Render tree
    renderFileTree(data.files || []);
  } catch (err) {
    console.error("Failed to load workspace:", err);
  }
}

function renderFileTree(files) {
  const container = document.getElementById("file-tree-container");
  if (!files || files.length === 0) {
    container.innerHTML = '<div style="color: var(--text-dim); padding: 12px;">No files found.</div>';
    return;
  }

  container.innerHTML = files
    .map((f) => {
      const icon = f.is_dir ? "📁" : getFileIcon(f.name);
      const isDirClass = f.is_dir ? "is-dir" : "";
      return `<div class="tree-item ${isDirClass}" onclick="openFile('${escapeHtml(f.path)}', ${f.is_dir})">
        <span>${icon}</span>
        <span>${escapeHtml(f.name)}</span>
      </div>`;
    })
    .join("");
}

function getFileIcon(name) {
  if (name.endsWith(".py")) return "🐍";
  if (name.endsWith(".js") || name.endsWith(".ts")) return "📜";
  if (name.endsWith(".json")) return "⚙️";
  if (name.endsWith(".md")) return "📝";
  if (name.endsWith(".html")) return "🌐";
  if (name.endsWith(".css")) return "🎨";
  if (name.endsWith(".kt")) return "📱";
  return "📄";
}

async function openFile(filePath, isDir) {
  if (isDir) return;
  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(filePath)}`);
    const data = await res.json();
    if (data.content !== undefined) {
      document.getElementById("active-file-title").textContent = filePath.split(/[\\/]/).pop();
      const codeViewer = document.getElementById("code-viewer-content");
      codeViewer.textContent = data.content;
      switchInspectorPane("code-pane");
      Prism.highlightElement(codeViewer);
    }
  } catch (err) {
    console.error("Failed to read file:", err);
  }
}

/* Load Models */
async function loadModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    const select = document.getElementById("model-select");
    const ollamaGroup = document.getElementById("ollama-models-group");

    if (data.ollama && data.ollama.length > 0) {
      ollamaGroup.innerHTML = data.ollama
        .map((m) => `<option value="ollama:${escapeHtml(m)}">${escapeHtml(m)} (Local)</option>`)
        .join("");
    }
    if (data.current) {
      select.value = data.current;
    }
  } catch (err) {
    console.error("Failed to load models:", err);
  }
}

/* Send Prompt & Chat Stream */
async function sendPrompt() {
  const input = document.getElementById("prompt-input");
  const prompt = input.value.trim();
  if (!prompt || isStreaming) return;

  // Add user message to UI
  appendMessage("user", prompt);
  input.value = "";
  isStreaming = true;
  document.getElementById("btn-send").disabled = true;

  // Create assistant message container for streaming
  const assistantBubble = appendMessage("assistant", "Thinking...");

  const selectedModel = document.getElementById("model-select").value;
  const [provider, model] = selectedModel.includes(":") ? selectedModel.split(":") : ["ollama", selectedModel];

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, provider, model }),
    });

    if (!res.ok) {
      assistantBubble.textContent = "Error: " + (await res.text());
      isStreaming = false;
      document.getElementById("btn-send").disabled = false;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    assistantBubble.innerHTML = "";
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = (buffer + chunk).split("\n");
      buffer = lines.pop(); // keep last incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.slice(6).trim();
        if (jsonStr === "[DONE]") break;

        try {
          const event = JSON.parse(jsonStr);
          handleStreamEvent(event, assistantBubble);
        } catch (e) {
          // not json, plain text
          assistantBubble.innerText += jsonStr;
        }
      }
    }
  } catch (err) {
    assistantBubble.innerText += `\n[Error: ${err.message}]`;
  } finally {
    isStreaming = false;
    document.getElementById("btn-send").disabled = false;
    checkPendingApprovals();
  }
}

function handleStreamEvent(event, bubble) {
  if (event.type === "text") {
    bubble.innerText += event.text;
    scrollMessages();
  } else if (event.type === "tool_start") {
    const toolEl = document.createElement("div");
    toolEl.className = "tool-pill";
    toolEl.id = `tool-${event.id}`;
    toolEl.innerHTML = `
      <div class="tool-header">
        <span>🔧 Running: <strong>${escapeHtml(event.name)}</strong></span>
        <span>${escapeHtml(JSON.stringify(event.arguments).slice(0, 40))}...</span>
      </div>
    `;
    bubble.appendChild(toolEl);
    scrollMessages();
  } else if (event.type === "tool_result") {
    const toolEl = document.getElementById(`tool-${event.id}`);
    if (toolEl) {
      toolEl.classList.add(event.is_error ? "error" : "success");
      const out = document.createElement("div");
      out.className = "tool-output";
      out.innerText = event.result.slice(0, 300);
      toolEl.appendChild(out);
    }
    // Also log to terminal tab
    const term = document.getElementById("terminal-logs");
    term.textContent += `\n$ ${event.name} -> ${event.result}\n`;
  } else if (event.type === "approval_needed") {
    showApprovalBanner(event.approval_id, event.summary);
  }
}

function appendMessage(role, text) {
  const container = document.getElementById("messages-container");
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;

  const header = document.createElement("div");
  header.className = "msg-header";
  header.innerText = role === "user" ? "You" : "🔨 Forge Assistant";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerText = text;

  row.appendChild(header);
  row.appendChild(bubble);
  container.appendChild(row);
  scrollMessages();
  return bubble;
}

function scrollMessages() {
  const container = document.getElementById("messages-container");
  container.scrollTop = container.scrollHeight;
}

function quickPrompt(text) {
  document.getElementById("prompt-input").value = text;
  sendPrompt();
}

/* Approvals Management */
async function checkPendingApprovals() {
  try {
    const res = await fetch("/api/approvals");
    const data = await res.json();
    const approvals = data.approvals || [];
    const countBadge = document.getElementById("nav-approval-count");

    if (approvals.length > 0) {
      countBadge.style.display = "block";
      countBadge.textContent = approvals.length;

      const first = approvals[0];
      showApprovalBanner(first.id, first.summary);
      renderDiffReview(first);
    } else {
      countBadge.style.display = "none";
      document.getElementById("approval-banner").style.display = "none";
      currentActiveApprovalId = null;
    }
  } catch (err) {
    // ignore polling error
  }
}

function showApprovalBanner(id, summary) {
  currentActiveApprovalId = id;
  const banner = document.getElementById("approval-banner");
  banner.style.display = "flex";
  document.getElementById("approval-banner-text").textContent = `Approval Required: ${summary}`;
}

function renderDiffReview(approval) {
  const diffContainer = document.getElementById("diff-content");
  diffContainer.innerHTML = `
    <div class="diff-header">
      Action: <strong>${escapeHtml(approval.action_type)}</strong> (ID: ${approval.id})
    </div>
    <div style="font-size: 13px; color: var(--text-muted);">
      ${escapeHtml(approval.summary)}
    </div>
    <div class="diff-line-del">- Proposed target: ${escapeHtml(JSON.stringify(approval.details))}</div>
    <div style="margin-top: 14px; display: flex; gap: 8px;">
      <button class="btn-approve" onclick="handleApproval('${approval.id}', 'approve')">✓ Approve Action</button>
      <button class="btn-reject" onclick="handleApproval('${approval.id}', 'reject')">✕ Reject Action</button>
    </div>
  `;
}

async function handleApproval(id, action) {
  try {
    await fetch(`/api/approvals/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    checkPendingApprovals();
  } catch (err) {
    console.error("Failed to submit approval:", err);
  }
}

/* Settings Modal */
function initSettingsModal() {
  const modal = document.getElementById("settings-modal");
  document.getElementById("btn-open-settings").addEventListener("click", async () => {
    try {
      const res = await fetch("/api/settings");
      const cfg = await res.json();
      document.getElementById("setting-provider").value = cfg.default_provider || "ollama";
      document.getElementById("setting-ollama-url").value = cfg.providers?.ollama?.base_url || "http://localhost:11434";
      document.getElementById("setting-openai-key").value = cfg.providers?.openai?.api_key || "";
      document.getElementById("setting-anthropic-key").value = cfg.providers?.anthropic?.api_key || "";
      document.getElementById("setting-gemini-key").value = cfg.providers?.gemini?.api_key || "";
      document.getElementById("setting-telegram-token").value = cfg.server?.telegram?.bot_token || "";
    } catch (err) {}
    modal.classList.add("open");
  });

  document.getElementById("btn-close-settings").addEventListener("click", () => modal.classList.remove("open"));
  document.getElementById("btn-cancel-settings").addEventListener("click", () => modal.classList.remove("open"));

  document.getElementById("btn-save-settings").addEventListener("click", async () => {
    const payload = {
      default_provider: document.getElementById("setting-provider").value,
      ollama_url: document.getElementById("setting-ollama-url").value,
      openai_key: document.getElementById("setting-openai-key").value,
      anthropic_key: document.getElementById("setting-anthropic-key").value,
      gemini_key: document.getElementById("setting-gemini-key").value,
      telegram_token: document.getElementById("setting-telegram-token").value,
    };
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    modal.classList.remove("open");
    loadModels();
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
