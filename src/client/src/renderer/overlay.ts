import "./overlay.css";

type OverlayPayload = {
  commentDisplay: string;
  quickReply: string;
  cue: string;
  createdAt: string;
};

type OverlayUpdate = {
  payload: OverlayPayload;
  fontScale: number;
  theme: "light" | "dark";
  opacity: number;
};

const root = document.querySelector<HTMLElement>("#overlay-app");

if (!root) {
  throw new Error("Overlay root element was not found.");
}

window.echocue.overlay.onUpdate((update: OverlayUpdate) => {
  root.style.setProperty("--overlay-scale", String(update.fontScale));
  root.style.setProperty("--overlay-shell-opacity", String(update.opacity));
  root.dataset.theme = update.theme;
  root.innerHTML = renderOverlay(update.payload);
});

function renderOverlay(payload: OverlayPayload): string {
  return `
    <section class="overlay-shell">
      <div class="overlay-drag-handle" title="拖动浮窗">
        <span class="overlay-brand">ECHO<span>/</span>CUE</span>
        <span class="overlay-time">${escapeHtml(payload.createdAt)}</span>
      </div>
      <div class="overlay-section">
        <span class="overlay-label">观众弹幕</span>
        <p class="overlay-comment">“${escapeHtml(payload.commentDisplay)}”</p>
      </div>
      <div class="overlay-divider"></div>
      <div class="overlay-grid">
        <div class="overlay-section">
          <span class="overlay-label">建议回复</span>
          <p>${escapeHtml(payload.quickReply)}</p>
        </div>
        <div class="overlay-section">
          <span class="overlay-label">提词</span>
          <p>${escapeHtml(payload.cue)}</p>
        </div>
      </div>
    </section>
  `;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character] ?? character);
}
