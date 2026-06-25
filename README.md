<div align="center">

# 台灣 AI 求職 Co-pilot · Taiwan AI Job Co-pilot

**A multi-agent job-search assistant for the Taiwan market — find jobs, audit your résumé, generate tailored application packages, and run mock interviews, end to end.**

Powered by your local **Claude Code / Codex CLI** subscription — no API key required, no API quota consumed.

**English** · [繁體中文](README.zh-TW.md)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3-06B6D4?logo=tailwindcss&logoColor=white)

</div>

> The application UI is in Traditional Chinese, tailored to Taiwan's job-search conventions (104 / Cake / Yourator / LinkedIn).

## Quick Start

> **Prerequisites:** Python 3.11+, Node.js 18+, and either a logged-in **Claude Code** (`claude`) / **Codex CLI** (`codex`) on your `PATH`, or an **Anthropic API key**.

```bash
git clone https://github.com/kevin333353/taiwan-ai-job-copilot.git
cd taiwan-ai-job-copilot

# One-time setup: virtualenv + backend deps + frontend install & build
setup.bat            # Windows
# ./setup.sh         # macOS / Linux / Git Bash

# Launch
desktop.bat          # native desktop window (recommended)
# run.bat            # web mode → http://localhost:8000
```

`setup.bat` / `setup.sh` does everything (venv, `pip install`, `npm install`, `npm run build`) in one go — no need to start the front and back ends separately.

Using the **API-key** backend instead of a CLI subscription? Copy `.env.example` to `.env` and set:

```env
LLM_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Running modes

| Mode             | Command                                                        | Notes                                                              |
| ---------------- | ------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Desktop app**  | `desktop.bat` (or `python desktop.py`)                        | Native window; first run shows a backend picker + connection test. |
| **Web**          | `run.bat` (or `python -m uvicorn app.server:app --port 8000`) | Open <http://localhost:8000>.                                     |
| **CLI (one JD)** | `python -m app.cli data/demo_jobs/ai_engineer.txt`           | Headless single-JD run.                                            |

> Switch the LLM backend from the onboarding screen, the top-right selector, or `LLM_BACKEND` in `.env`.

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [LLM Backends](#llm-backends)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Auto job search** — paste or upload a résumé; the system derives keywords, searches 104 / Yourator / LinkedIn / Cake **in parallel**, and ranks results by fit in **streaming batches** (results appear as they are scored). Includes an adjustable "≥ N score" slider, pagination, and a per-company section for employers you name explicitly.
- **Skill-gap analysis** — aggregates the in-demand skills across matched jobs and contrasts them with your résumé to surface real gaps.
- **Search history** — every search is auto-saved (AI picks + named-company jobs + skill gap); revisit, regenerate a package, or delete. No more losing a great match to a re-run.
- **Résumé health check** — scores against Taiwan ATS conventions with concrete fixes and before/after rewrites.
- **Application-package workbench** — a multi-agent pipeline (parse JD → match score → company research → tailored résumé → cover letter → interview kit → critique) with a **human approval gate**. Outputs are editable inline and exportable to Word / PDF, then auto-saved.
- **Mock interview** — generates questions from the JD and your résumé, with per-answer feedback, scores, and a final summary.
- **Personalization** — remembers your most recent résumé (no re-upload) and preferences (target titles, tone, skills to emphasize) across sessions and applies them to outputs.

## LLM Backends

| Backend      | Auth                     | Notes                                              |
| ------------ | ------------------------ | -------------------------------------------------- |
| `claude_cli` | Claude Code subscription | **Default.** No API key; strips `ANTHROPIC_*` env. |
| `codex_cli`  | Codex subscription       | Uses your configured Codex model.                  |
| `anthropic`  | `ANTHROPIC_API_KEY`      | Cloud/deployable; pay-per-use.                     |

CLI subscriptions run **locally** and bind to the logged-in CLI on your machine — a remote server cannot use someone else's local subscription. For a fully hosted deployment, use the `anthropic` backend.

## Architecture

```
React SPA (Vite)  ──HTTP/SSE──►  FastAPI
                                   │
                  ┌────────────────┼─────────────────────┐
                  ▼                ▼                     ▼
          LangGraph StateGraph   Job sources        App SQLite
          (agents + human gate)  104/Yourator/      (history /
          SqliteSaver checkpoint  LinkedIn/Cake      memory / searches)
                  │
                  ▼
          Pluggable LLM backend
          claude_cli · codex_cli · anthropic
```

- A LangGraph `StateGraph` orchestrates the agents; `SqliteSaver` persists checkpoints and powers the human-in-the-loop approval gate via `interrupt()` / `Command(resume=…)`.
- The server streams progress to the browser over **Server-Sent Events**.
- An application-level SQLite database (separate from the LangGraph checkpoint store) holds package history, user memory, and saved searches.
- Models are tiered automatically: **haiku** for extraction, **sonnet** for matching/generation, **opus** for the Critic/Supervisor.

## Tech Stack

| Layer    | Technologies                                                             |
| -------- | ------------------------------------------------------------------------ |
| Backend  | Python, FastAPI, LangGraph, LangChain, Pydantic v2, SQLite, BeautifulSoup |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, lucide-react                    |
| LLM      | Claude Code CLI / Codex CLI (subscription) · Anthropic API (key)          |
| Desktop  | pywebview (native window over the local server)                          |

## Project Structure

```
app/
  agents/     # résumé eval, job search, company research, skill gap, interview sim, …
  sources/    # 104 / Yourator / LinkedIn / Cake search + registry
  store/      # app-level SQLite: history, memory, searches
  intake/     # résumé/JD parsing and fetching
  export/     # Word/PDF export
  graph.py    # LangGraph StateGraph (agents + human gate)
  server.py   # FastAPI + SSE endpoints
  llm.py      # pluggable LLM backend resolution
frontend/     # Vite + React + TS + Tailwind SPA
tests/        # pytest suite
data/         # demo profiles/jobs, fallback data
```

## Testing

```bash
pytest                # unit/integration suite (live API tests skipped by default)
pytest -m live        # include tests that call the real API
cd frontend && npm run build   # type-check + production build
```

## Roadmap

- [ ] Single-file desktop binary (PyInstaller) for non-developers
- [ ] Hosted (bring-your-own-API-key) deployment mode
- [ ] More job sources

## Contributing

Issues and pull requests are welcome. For non-trivial changes, please open an issue first to discuss the approach. Run `pytest` and `npm run build` before submitting.

## License

No license has been chosen yet. Until a `LICENSE` file is added, all rights are reserved by the author.
