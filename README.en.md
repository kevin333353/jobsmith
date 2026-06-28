<div align="center">

<img src="https://raw.githubusercontent.com/kevin333353/jobsmith/master/frontend/public/logo512.png" alt="Jobsmith logo" width="84" height="84" />

# Jobsmith

**An open-source, multi-agent AI co-pilot for the Taiwan job market.**

Find jobs, audit your résumé, and generate tailored application packages — résumé, cover letter, interview prep, and company research. Generation runs **in the background** (it keeps going if you navigate away or refresh, and multiple jobs run in parallel); you watch the live multi-agent trace, then review and approve each package in your library.

Runs through your own **Claude Code / Codex CLI** subscription (no separate API key required) — or **bring your own key** for any OpenAI-compatible model.

[繁體中文](README.md) · [**Download (Windows / unsigned macOS)**](#download) · [Quick Start](#quick-start-from-source) · [Architecture](#architecture) · [Privacy](docs/PRIVACY.md)

![License](https://img.shields.io/badge/License-Apache_2.0-green)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Platform](https://img.shields.io/badge/Windows-64--bit-0078D6?logo=windows&logoColor=white)
![Platform](https://img.shields.io/badge/macOS-unsigned-lightgrey?logo=apple)

</div>

> The app UI is in Traditional Chinese, tailored to Taiwan's job-search conventions (104 / Cake / Yourator / LinkedIn). Data is stored locally by default; when you run AI features, your résumé and prompts are handled by the CLI or BYOK backend you choose. See [Privacy and Data Handling](docs/PRIVACY.md).

---

## Feature Overview

- **Auto job search**: upload a resume, let AI derive keywords, and search 104 / Yourator / LinkedIn / Cake.
- **Ranked results**: stream search results, score fit, and open the right jobs for an application package.
- **Package workbench**: generate tailored resume bullets, cover letters, interview prep, and company research.
- **Resume health check**: audit ATS fit, show deep-check or fallback status, and keep local report history.

---

## Download

**Windows**

**[⬇ Download Jobsmith for Windows (64-bit)](https://github.com/kevin333353/jobsmith/releases/latest/download/Jobsmith.exe)** — a single `.exe`. No Python or Node.js required.

1. Grab `Jobsmith.exe` from the [latest release](https://github.com/kevin333353/jobsmith/releases/latest).
2. Double-click it. A native window opens (the first launch unpacks for ~10–30s).
3. In the **top-right control panel**, choose your AI engine:
   - **Local CLI** — a logged-in **Claude Code** (`claude`) or **Codex CLI** (`codex`) on your `PATH`, **or**
   - **BYOK** — `base_url` + `api_key` + `model` for any OpenAI-compatible endpoint (OpenAI, DeepSeek, Gemini, Groq, OpenRouter, Ollama, LM Studio, vLLM…).

> **Requirements:** Windows 10/11 (64-bit; WebView2 is built into Windows 11). Your history, settings, and `.env` are saved next to the `.exe`; Jobsmith does not operate a hosted backend, and AI requests go only to the backend you choose.

**macOS**

- **[⬇ Download Jobsmith for macOS Apple Silicon](https://github.com/kevin333353/jobsmith/releases/latest/download/Jobsmith-macOS-arm64-unsigned.dmg)** — M1 / M2 / M3 / M4
- **[⬇ Download Jobsmith for macOS Intel](https://github.com/kevin333353/jobsmith/releases/latest/download/Jobsmith-macOS-x64-unsigned.dmg)** — Intel Macs

The macOS build is an **unsigned** `.dmg`. It is not signed with an Apple Developer ID and is not notarized, so first launch may trigger Gatekeeper. Open the DMG, drag `Jobsmith.app` to Applications, then use right-click → **Open**, or allow the app in System Settings.

The macOS app stores data and `.env` in `~/Library/Application Support/Jobsmith`.

Maintainers can run **Actions → Build unsigned macOS DMG** manually; the workflow has a `publish_release=true` option that replaces the DMG files on a chosen release tag.

## Quick Start (from source)

> **Prerequisites:** Python 3.11+, Node.js 20.19+ / 22.13+ / 24+, and a logged-in **Claude Code** (`claude`) or **Codex CLI** (`codex`) on your `PATH` (or a BYOK key).

```bash
git clone https://github.com/kevin333353/jobsmith.git
cd jobsmith

setup.bat            # Windows  — one-time setup (venv + deps + frontend build)
# ./setup.sh         # macOS / Linux / Git Bash

desktop.bat          # launch as a native desktop window (recommended)
# run.bat            # or web mode → http://localhost:8000
```

| Mode             | Command                                                        | Notes                                                              |
| ---------------- | ------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Desktop app**  | `desktop.bat` (or `python desktop.py`)                        | Native window; first run shows a backend picker.                   |
| **Web**          | `run.bat` (or `python -m uvicorn app.server:app --port 8000`) | Open <http://localhost:8000>.                                     |
| **CLI (one JD)** | `python -m app.cli data/demo_jobs/ai_engineer.txt`           | Headless single-JD run.                                            |

To build your own Windows `.exe`: `pip install pyinstaller && pyinstaller jobsmith.spec --noconfirm` → `dist/Jobsmith.exe`.
To build the unsigned macOS `.app`, build the frontend on macOS and run: `python -m PyInstaller jobsmith-macos.spec --noconfirm --clean` → `dist/Jobsmith.app`.

## Table of Contents

- [Feature Overview](#feature-overview)
- [Download](#download)
- [Quick Start](#quick-start-from-source)
- [Features](#features)
- [LLM Backends](#llm-backends)
- [Privacy and Data](#privacy-and-data)
- [Architecture](#architecture)
- [Evaluation](#evaluation)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)

## Features

- **Auto job search** — paste or upload a résumé; the system derives keywords and searches 104 / Yourator / LinkedIn / Cake **in parallel**, ranking by fit in **streaming batches** (results appear as they're scored). Pick your **region(s) before searching** (applied at-source on 104, result-side on the others), filter by **fit band** (high / mid-and-up / all), set pages per source, and track named companies in a separate section.
- **Search history** — every search is auto-saved; revisit it, regenerate a package, or delete it.
- **Résumé health check** — scores against Taiwan ATS conventions with concrete fixes and before/after rewrites.
- **Application-package workbench** — click *Generate* on any job and a multi-agent pipeline (parse JD → match score → company research → tailored résumé → cover letter → interview kit → critique) runs **in the background**: it keeps going if you navigate away or refresh the page, and several jobs run **in parallel**. The workbench is a clean, single-screen viewer — a live agent-orchestration trace on the left, the finished documents paginated on the right.
- **My packages (library)** — every generated package lands here with a status (in-progress → pending review → approved). **Review, approve, or delete** each, re-open one to the workbench, launch a mock interview from it, and export to **Word (.docx)** (PDF via the browser's print dialog).
- **Mock interview** — generates questions from the JD and your résumé, with per-answer feedback and scores. Start from any saved package or a pasted JD; **each job gets its own conversation tab**, so you can run several mock interviews side by side without overwriting.
- **Personalization** — remembers your most recent résumé (no re-upload) and preferences (target titles, tone, skills to emphasize) across sessions, and applies them to outputs.

## LLM Backends

Pick your AI engine from the **top-right control panel** — a **local CLI subscription** (no API key) or **BYOK** (any OpenAI-compatible endpoint). Selecting a backend takes effect immediately; the **Test** button is an optional connection check, never a gate. Local CLIs offer a **rescan** action and a **selectable model**.

| Backend      | Auth                                   | Notes                                                                                                    |
| ------------ | -------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `claude_cli` | Claude Code subscription               | **Default.** No API key; strips `ANTHROPIC_*` env. Model selectable (auto-tiered by default).            |
| `codex_cli`  | Codex subscription                     | No API key. Model selectable; defaults to your Codex config.                                             |
| `openai`     | BYOK — any OpenAI-compatible endpoint  | `base_url` + `api_key` + `model`. Works with OpenAI, DeepSeek, Gemini, Groq, OpenRouter, Ollama, LM Studio, vLLM… |

CLI backends call the corresponding provider through the logged-in CLI on your machine. BYOK calls the OpenAI-compatible endpoint you configure. Jobsmith does not operate a hosted backend or send your data to the project maintainer's server. BYOK credentials are written only to your local `.env`. An API-key backend (`anthropic`) also exists for self-hosting or CI.

## Privacy and Data

Jobsmith stores profile memory, preferences, searches, generated packages, `.env`, and error logs locally. You can open **Settings → Clear personal data** to remove resume memory, searches, and generated package history; AI backend settings are kept so you do not need to re-enter API keys.

When you run AI features, your résumé, job descriptions, and prompts are sent to the AI backend you selected. Read [Privacy and Data Handling](docs/PRIVACY.md) before using the app with sensitive data.

## Architecture

```
React SPA (Vite)  ──HTTP · SSE · poll──►  FastAPI
                                            │
                  ┌─────────────────────────┼────────────────────────┐
                  ▼                         ▼                       ▼
        LangGraph StateGraph           Job sources             App SQLite
        (one per background run,       104 / Yourator /        (packages w/ status
         own in-memory checkpoint,     LinkedIn / Cake          進行中→待審→已核可,
         runs in parallel)                                      memory, searches)
                  │
                  ▼
          Pluggable LLM backend
          claude_cli · codex_cli · openai (BYOK)
```

- **Background generation:** each *Generate* spins up its own LangGraph `StateGraph` with a private in-memory checkpointer, run on a small thread pool — so jobs run **in parallel** and survive client disconnects (refresh / navigation). The browser **polls** `/api/run/events` for live progress; the finished package is written to the app database. This decouples the run from the HTTP request — closing the tab doesn't stop it.
- **Job search** streams results to the browser over **Server-Sent Events** as each source returns and each job is scored.
- An application-level SQLite database holds packages with a lifecycle status (in-progress → pending review → approved), user memory, and saved searches; you review and approve in **My packages**. _(The standalone CLI still uses a resumable, file-backed human-approval gate via `interrupt()` / `Command(resume=…)`.)_
- On the CLI backends, models are tiered automatically: **haiku** for extraction, **sonnet** for matching/generation, **opus** for the Critic/Supervisor (overridable per backend).

## Evaluation

Does the Supervisor reflection loop (Critic → revise un-passed documents → re-critique) actually improve output quality? A small golden set of 5 job/résumé pairs is run with reflection **off** (no revisions) and **on**, and the resulting Critic scores are compared:

<!-- EVAL:START -->
| Reflection | Critic pass rate | Mean quality score |
| ---------- | ---------------- | ------------------ |
| Off        | 60% (3/5)        | 85.6               |
| **On**     | **100% (5/5)**   | **87.5**           |

Reflection lifts the Critic pass rate by **+40pp** (60% → 100%) and mean quality by **+1.9** (85.6 → 87.5) across the 5 golden cases. Both "off" failures were cover letters making **unverified company claims** or an **unsupported experience claim** — exactly what the Critic → revise loop catches. _(One harness run; LLM calls are non-deterministic, so exact numbers vary run to run.)_
<!-- EVAL:END -->

```bash
python -m app.evals.harness     # runs the graph on each golden case, writes app/evals/results.json
```

The `summarize()` step is a pure function with its own unit tests, so the aggregation logic is verified independently of the (non-deterministic) LLM calls.

## Tech Stack

| Layer    | Technologies                                                               |
| -------- | -------------------------------------------------------------------------- |
| Backend  | Python, FastAPI, LangGraph, LangChain, Pydantic v2, SQLite, BeautifulSoup  |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, lucide-react                     |
| LLM      | Claude Code CLI / Codex CLI (local) · any OpenAI-compatible endpoint (BYOK) |
| Desktop  | pywebview (native window) · PyInstaller (single-file `.exe` / unsigned `.app`, distributed as `.dmg` on macOS) |

## Project Structure

```
app/
  agents/     # résumé eval, job search, company research, refine chat, interview sim, …
  sources/    # 104 / Yourator / LinkedIn / Cake search + registry + region map
  store/      # app-level SQLite: history, memory, searches
  intake/     # résumé/JD parsing and fetching
  export/     # Word (.docx) export
  graph.py    # LangGraph StateGraph (agents + human gate)
  server.py   # FastAPI + SSE endpoints
  llm.py      # pluggable LLM backend resolution
frontend/     # Vite + React + TS + Tailwind SPA
tests/        # pytest suite
desktop.py    # native-window launcher    jobsmith.spec / jobsmith-macos.spec  # PyInstaller build
```

## Testing

```bash
pytest                         # unit/integration suite (live API tests skipped by default)
pytest -m live                 # include tests that call the real API
cd frontend && npm run lint    # frontend lint
cd frontend && npm run build   # type-check + production build
```

## Roadmap

- [x] Single-file Windows desktop app (PyInstaller)
- [x] unsigned macOS `.dmg` GitHub Actions build
- [x] BYOK — any OpenAI-compatible backend
- [x] Background, refresh-proof package generation with parallel runs
- [ ] macOS signing and notarization
- [ ] Linux builds
- [ ] More job sources

## Contributing

Issues and pull requests are welcome. For non-trivial changes, please open an issue first to discuss the approach. Run `pytest`, `npm run lint`, and `npm run build` before submitting. Before publishing a Windows `.exe`, run the clean-environment smoke test in the [Release Checklist](docs/RELEASE_CHECKLIST.md).

## Disclaimer

This project is for **personal, educational, and research use**. It queries public job listings from 104 / Yourator / LinkedIn / Cake at low frequency to help an individual job seeker. You are responsible for complying with each site's Terms of Service and `robots.txt`; do **not** use it for bulk scraping or commercial data harvesting. The software is provided "as is", without warranty of any kind. LLM-generated content (résumés, cover letters, company research) may contain inaccuracies — always review before use.

## License

Released under the [Apache License 2.0](LICENSE).
