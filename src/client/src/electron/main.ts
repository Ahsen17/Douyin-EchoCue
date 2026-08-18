import { app, BrowserWindow } from "electron";
import { join } from "node:path";

const isDevelopment = !app.isPackaged;
const rendererUrl = process.env.ECHOCUE_RENDERER_URL ?? "http://127.0.0.1:5173";

function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 960,
    minHeight: 640,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: join(__dirname, "preload.js"),
      additionalArguments: [isDevelopment ? "--echocue-development" : "--echocue-production"],
    },
  });

  window.once("ready-to-show", () => {
    window.show();
  });

  if (isDevelopment) {
    void window.loadURL(rendererUrl);
  } else {
    void window.loadFile(join(__dirname, "../dist/index.html"));
  }

  return window;
}

app.whenReady().then(() => {
  createMainWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
