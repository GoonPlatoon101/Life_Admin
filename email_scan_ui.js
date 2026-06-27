(function () {
  const state = {
    modal: null,
    preview: null,
    running: false
  };

  function installStyles() {
    const style = document.createElement("style");
    style.textContent = `
      .email-scan-backdrop {
        position: fixed;
        inset: 0;
        display: none;
        place-items: center;
        padding: 16px;
        background: rgba(23, 32, 27, 0.36);
        z-index: 30;
      }
      .email-scan-backdrop.open { display: grid; }
      .email-scan-modal {
        width: min(520px, 100%);
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
        color: var(--ink);
        box-shadow: var(--shadow);
      }
      .email-scan-head,
      .email-scan-actions {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 16px;
        border-bottom: 1px solid var(--line);
      }
      .email-scan-actions {
        border-top: 1px solid var(--line);
        border-bottom: 0;
      }
      .email-scan-body {
        display: grid;
        gap: 12px;
        padding: 16px;
      }
      .email-scan-field {
        display: grid;
        gap: 6px;
      }
      .email-scan-field span {
        color: var(--muted);
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }
      .email-scan-field input,
      .email-scan-field select {
        min-height: 40px;
        padding: 0 10px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface-soft);
        color: var(--ink);
      }
      .email-scan-preview {
        position: fixed;
        left: 264px;
        right: 22px;
        bottom: 20px;
        display: none;
        max-height: min(360px, 50vh);
        overflow: auto;
        padding: 14px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
        box-shadow: var(--shadow);
        z-index: 21;
      }
      .email-scan-preview.open { display: grid; gap: 10px; }
      .email-source-card {
        padding: 10px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface-soft);
      }
      .email-source-card strong,
      .email-source-card span {
        display: block;
      }
      .email-source-card span {
        margin-top: 4px;
        color: var(--muted);
        font-size: 12px;
      }
      @media (max-width: 720px) {
        .email-scan-preview {
          left: 12px;
          right: 12px;
          bottom: 12px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function createModal() {
    const backdrop = document.createElement("div");
    backdrop.className = "email-scan-backdrop";
    backdrop.innerHTML = `
      <form class="email-scan-modal" id="emailScanForm">
        <div class="email-scan-head">
          <div>
            <p class="eyebrow">Read-only scanner</p>
            <h2>Connect email source</h2>
          </div>
          <button class="drawer-close" type="button" data-email-scan-close title="Close">x</button>
        </div>
        <div class="email-scan-body">
          <label class="email-scan-field">
            <span>Provider</span>
            <select id="emailScanProvider">
              <option value="google">Gmail</option>
              <option value="outlook">Outlook</option>
            </select>
          </label>
          <label class="email-scan-field">
            <span>Read-only access token</span>
            <input id="emailScanToken" type="password" autocomplete="off" required />
          </label>
          <label class="email-scan-field">
            <span>Query</span>
            <input id="emailScanQuery" type="text" placeholder="newer_than:7d" />
          </label>
          <label class="email-scan-field">
            <span>Max messages</span>
            <input id="emailScanMax" type="number" min="1" max="25" value="10" />
          </label>
          <p class="empty-state">The token is sent only to the local scanner endpoint and is not passed to the agent.</p>
        </div>
        <div class="email-scan-actions">
          <button class="text-button" type="button" data-email-scan-close>Cancel</button>
          <button class="primary-button" id="emailScanSubmit" type="submit">Scan inbox</button>
        </div>
      </form>
    `;
    document.body.appendChild(backdrop);
    state.modal = backdrop;

    backdrop.querySelectorAll("[data-email-scan-close]").forEach((button) => {
      button.addEventListener("click", closeModal);
    });
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) closeModal();
    });
    backdrop.querySelector("#emailScanForm").addEventListener("submit", runScan);
  }

  function createPreview() {
    const preview = document.createElement("section");
    preview.className = "email-scan-preview";
    preview.setAttribute("aria-live", "polite");
    document.body.appendChild(preview);
    state.preview = preview;
  }

  function openModal() {
    state.modal.classList.add("open");
    state.modal.querySelector("#emailScanToken").focus();
  }

  function closeModal() {
    state.modal.classList.remove("open");
  }

  function showToast(message) {
    const toast = document.querySelector("#toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 2400);
  }

  function renderPreview(result) {
    const items = result.source_items || [];
    const rows = items.map((item) => `
      <article class="email-source-card">
        <strong>${escapeHtml(item.title || "(no subject)")}</strong>
        <span>${escapeHtml(item.provider || result.provider)} - ${escapeHtml(item.source_id || "")}</span>
        <span>${escapeHtml((item.content || "").slice(0, 220))}</span>
      </article>
    `).join("");

    state.preview.innerHTML = `
      <div class="email-scan-head">
        <div>
          <p class="eyebrow">Scanner result</p>
          <h2>${items.length} email source items</h2>
        </div>
        <button class="drawer-close" type="button" id="closeEmailPreview" title="Close">x</button>
      </div>
      ${rows || '<p class="empty-state">No email messages matched this scan.</p>'}
    `;
    state.preview.classList.add("open");
    state.preview.querySelector("#closeEmailPreview").addEventListener("click", () => {
      state.preview.classList.remove("open");
    });
  }

  async function runScan(event) {
    event.preventDefault();
    if (state.running) return;

    const submit = state.modal.querySelector("#emailScanSubmit");
    state.running = true;
    submit.disabled = true;
    submit.textContent = "Scanning...";

    const payload = {
      provider: state.modal.querySelector("#emailScanProvider").value,
      access_token: state.modal.querySelector("#emailScanToken").value,
      query: state.modal.querySelector("#emailScanQuery").value,
      max_results: Number(state.modal.querySelector("#emailScanMax").value || 10)
    };

    try {
      const response = await fetch("/api/email/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Email scan failed.");
      closeModal();
      renderPreview(result);
      showToast(`Read-only scan returned ${result.count} email source items.`);
    } catch (error) {
      showToast(error.message || "Email scan failed.");
    } finally {
      state.running = false;
      submit.disabled = false;
      submit.textContent = "Scan inbox";
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function installRunButtonBridge() {
    const button = document.querySelector("#runAgentBtn");
    if (!button) return;

    button.addEventListener("click", (event) => {
      event.stopImmediatePropagation();
      openModal();
    }, true);
  }

  installStyles();
  createModal();
  createPreview();
  installRunButtonBridge();
})();
