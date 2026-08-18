import "./styles.css";

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Renderer root element was not found.");
}

const platform = window.echocue.platform;
const mode = window.echocue.isDevelopment ? "development" : "production";

app.innerHTML = `
  <section class="shell">
    <div class="brand-mark" aria-hidden="true">EC</div>
    <p class="eyebrow">Douyin-EchoCue</p>
    <h1>Client foundation ready</h1>
    <p class="description">
      Electron main, preload and renderer boundaries are connected.
      Business state and backend adapters will be added in the next stage.
    </p>
    <dl class="runtime">
      <div>
        <dt>Platform</dt>
        <dd>${platform}</dd>
      </div>
      <div>
        <dt>Mode</dt>
        <dd>${mode}</dd>
      </div>
    </dl>
  </section>
`;
