# EchoCue Client

This directory contains the Windows client prototype built with Electron and
TypeScript. It is intentionally independent from the Python backend during the
M6 Mock-first stages.

## Prerequisites

- Node.js 24 or newer
- npm 10 or newer
- Windows verification environment for Electron window behavior

## Commands

Run commands from `src/client/`:

```bash
npm install
npm run typecheck
npm run build
npm run dev
npm run package:win
```

`npm run dev` starts Vite, compiles Electron main/preload code in watch mode,
and launches the Electron main window. `npm run build` creates the renderer
bundle in `dist/` and Electron files in `dist-electron/`. `npm run package:win`
builds Windows NSIS and portable targets into `release/`.

## Boundaries

- `src/electron/main.ts`: Electron application lifecycle and main window.
- `src/electron/preload.ts`: the restricted renderer bridge.
- `src/renderer/`: browser-side UI and styles.
- `vite.config.ts`: renderer development and production build configuration.

The renderer must use the preload bridge for privileged capabilities. Mock
adapters and business state are intentionally deferred to M6 Stage 2 and Stage
4.

## Install Troubleshooting

If `npm install` fails while running `node_modules/electron/install.js`, the
Electron runtime download was interrupted. This directory includes a local
`.npmrc` that uses npm and Electron mirrors.

Retry from `src/client/`:

```bash
npm install
```

If a previous install left a partial Electron package, rebuild it:

```bash
npm rebuild electron
```
