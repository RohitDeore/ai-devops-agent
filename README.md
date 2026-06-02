# 🤖 AI DevOps Autonomous Incident Response Agent

> **Reduce MTTR automatically.** An AI-powered DevOps agent that monitors logs,
> detects anomalies, performs root-cause analysis, decides the optimal remediation
> action, executes it (or simulates it), and reports the full incident — all
> without human intervention.

---

## Table of Contents

1. [Project Description](#project-description)
2. [Architecture](#architecture)
3. [How the Agent Works](#how-the-agent-works)
4. [Features](#features)
5. [Setup & Installation](#setup--installation)
6. [Running the Project](#running-the-project)
7. [API Reference](#api-reference)
8. [Dashboard Guide](#dashboard-guide)
9. [Configuration](#configuration)
10. [Azure AI Foundry Integration](#azure-ai-foundry-integration)
11. [Docker Deployment](#docker-deployment)
12. [Testing](#testing)
13. [Project Structure](#project-structure)

---

## Project Description

This project implements a production-ready **AI DevOps Autonomous Incident
Response Agent** that sits between your log stream and your on-call team.
Instead of waking an engineer for every alert, the agent:

- Continuously **observes** application logs
- **Detects** errors, warnings, timeouts, and failures
- **Reasons** about the root cause using rule-based logic, OpenAI GPT, or
  **Microsoft Azure AI Foundry** (multi-step chain-of-thought reasoning)
- **Decides** the best remediation based on a priority action matrix
- **Acts** by simulating (or executing) restart / failover / scale-up commands
- **Reports** a structured JSON incident report for audit and post-mortems

The result is dramatically lower Mean-Time-To-Resolution (MTTR) and fewer 3 AM pages.

---

## Architecture

```
+----------------------------------------------------------+
|                        Agent Loop                        |
|                                                          |
|  logs/app.log                                            |
|       |                                                  |
|       v                                                  |
|  +----------+   +----------+   +----------------------+ |
|  | Observer |-->| Analyzer |-->|  Reasoner            | |
|  +----------+   +----------+   |  (Rule / OpenAI /    | |
|   (Observe)      (Analyze)     |   Azure AI Foundry)  | |
|                                +----------+-----------+ |
|                                           v             |
|              +----------+   +-------------------------+ |
|              | Reporter |<--|  Decision + Actuator     | |
|              +----------+   +-------------------------+ |
|               (Report)         (Decide + Act)           |
+----------------------------------------------------------+
         |                            |
         v                            v
  Flask REST API              Streamlit Dashboard
  (API key auth,              (ui/dashboard.py)
   rate limiting,
   report persistence)
```

### Module Responsibilities

| Module | Phase | Responsibility |
|---|---|---|
| `observer.py` | **Observe** | Read full / incremental log lines from file |
| `analyzer.py` | **Analyze** | Classify severity & issue type per log line |
| `reasoner.py` | **Reason** | Rule-based or OpenAI root-cause analysis |
| `foundry_reasoner.py` | **Reason** | Azure AI Foundry multi-step reasoning engine |
| `decision.py` | **Decide** | Map severity + issue type to action code |
| `actuator.py` | **Act** | Execute (or simulate) the chosen action |
| `reporter.py` | **Report** | Generate structured JSON incident reports |

---

## How the Agent Works

### The Agent Loop: Observe -> Analyze -> Reason -> Decide -> Act -> Report

#### 1. Observe
`LogObserver` reads `logs/app.log`. Two modes:
- **Full read** - all lines (used for analysis runs).
- **Incremental read** - only new lines since the last call (for live polling).

#### 2. Analyze
`LogAnalyzer` scans each line for severity keywords:

| Severity | Keywords |
|---|---|
| CRITICAL | CRITICAL, FATAL, CRASH, OUTOFMEMORY |
| ERROR | ERROR, FAILED, FAILURE, EXCEPTION, REFUSED |
| WARNING | WARNING, WARN, TIMEOUT, DEGRADED, SPIKE |

#### 3. Reason
Three reasoning engines available (auto-selected by config):

| Engine | Speed | Cost | Quality |
|---|---|---|---|
| **Rule-Based** (default) | Instant | Free | Good for known patterns |
| **OpenAI GPT** | ~1s | Pay-per-use | Better context understanding |
| **Azure AI Foundry** | ~2s | Pay-per-use | Best - full 4-step chain-of-thought |

Azure AI Foundry performs genuine multi-step reasoning:
1. **Understand** - reads log context fully
2. **Root Cause** - determines *why*, not just *what*
3. **Options** - lists 3 remediation paths with trade-offs
4. **Recommendation** - picks the best action with confidence score

#### 4. Decide
`DecisionEngine` consults a two-dimensional action matrix:

```
CRITICAL + DATABASE_ISSUE  --> FAILOVER_DATABASE
ERROR    + SERVICE_ISSUE   --> RESTART_SERVICE
WARNING  + RESOURCE_ISSUE  --> SCALE_UP_RESOURCES
```

#### 5. Act
`ActionActuator` executes the chosen action. In **simulation mode** (default),
every action is logged without touching real infrastructure. Production hooks
support Kubernetes (`kubectl`), AWS CLI, PagerDuty, and Slack.

#### 6. Report
`IncidentReporter` produces a structured JSON document per issue:

```json
{
  "incident_id": "INC-20260602-ISSUE-0004",
  "severity": "CRITICAL",
  "root_cause": "Port 5432 refused - PostgreSQL process likely crashed or OOM killed",
  "action_taken": "FAILOVER_DATABASE",
  "status": "RESOLVED",
  "reasoning_steps": {
    "step1_context": "...",
    "step2_root_cause": "...",
    "step3_options": ["...", "...", "..."],
    "step4_recommendation": "..."
  }
}
```

---

## Features

- Real-time log file monitoring with incremental reads
- Multi-level severity detection (CRITICAL / ERROR / WARNING)
- Seven issue type classifiers (DB, timeout, resource, auth, service, API, network)
- Rule-based RCA knowledge base (no external dependency)
- Optional OpenAI GPT integration for AI-powered RCA
- **Microsoft Azure AI Foundry** - 4-step chain-of-thought reasoning
- Automatic engine fallback (Foundry -> OpenAI -> Rule-Based)
- Priority-sorted action matrix
- Full simulation mode - safe to run without real infrastructure
- Production hooks: Kubernetes, AWS CLI, PagerDuty, Slack
- Flask REST API with authentication (`X-API-Key` header) and rate limiting
- Report persistence to `reports/` folder with history endpoint
- Streamlit dashboard with reasoning engine selector
- 81 unit + integration tests (pytest)
- Docker + docker-compose deployment

---

## Setup & Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/RohitDeore/ai-devops-agent.git
cd ai-devops-agent

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment variables
copy .env.example .env
```

Edit `.env` and set at minimum:

```
API_KEY=your-random-secret-here
```

---

## Running the Project

### Start the Streamlit Dashboard

```bash
python -m streamlit run ui/dashboard.py
```

Opens automatically at **http://localhost:8501**

### Start the Flask API

```bash
python run.py
```

API available at **http://localhost:5000**

### Production (Gunicorn)

```bash
gunicorn run:app --bind 0.0.0.0:5000 --workers 4
```

---

## API Reference

All endpoints (except `/health`) require the header:

```
X-API-Key: <your API_KEY from .env>
```

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness probe (no auth) |
| `/logs` | GET | Return log lines (`?lines=50`) |
| `/analyze` | POST | Run full pipeline |
| `/report` | GET | Full incident report |
| `/report/summary` | GET | Executive summary only |
| `/report/history` | GET | List persisted reports |
| `/logs/write` | POST | Append a log entry |

---

## Dashboard Guide

| Tab | Contents |
|---|---|
| **Log Monitor** | Colour-coded log viewer with auto-refresh and tail control |
| **Analysis** | Per-issue expanders with root cause and Foundry reasoning steps |
| **Actions** | Sortable table of remediation actions + distribution chart |
| **Reports** | Executive summary + per-incident JSON + download button |

**Sidebar - Reasoning Engine selector:**

| Option | Description |
|---|---|
| **Rule-Based (free)** | Fast keyword-based RCA, no credentials needed |
| **OpenAI** | GPT-powered RCA - enter your OpenAI API key |
| **Azure AI Foundry** | 4-step chain-of-thought - enter Foundry endpoint + key |

---

## Configuration

All settings loaded from `.env` (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(random)* | REST API authentication key |
| `SIMULATION_MODE` | `true` | Safe mode - no real infra calls |
| `LOG_FILE_PATH` | `logs/app.log` | Log file to monitor |
| `USE_AI_REASONING` | `false` | Enable OpenAI RCA |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `USE_FOUNDRY` | `false` | Enable Azure AI Foundry |
| `AZURE_FOUNDRY_ENDPOINT` | *(empty)* | Azure OpenAI endpoint URL |
| `AZURE_FOUNDRY_API_KEY` | *(empty)* | Azure OpenAI API key |
| `AZURE_FOUNDRY_DEPLOYMENT` | `gpt-4o-mini` | Deployment name |
| `RATE_LIMIT` | `60` | Requests per minute per IP |
| `FLASK_PORT` | `5000` | Flask server port |

---

## Azure AI Foundry Integration

### Setup

1. Create an Azure AI Foundry hub and deploy a model (e.g. `gpt-4o-mini`)
2. Set in `.env`:

```env
USE_FOUNDRY=true
AZURE_FOUNDRY_ENDPOINT=https://<your-hub>.openai.azure.com/
AZURE_FOUNDRY_API_KEY=<your-azure-key>
AZURE_FOUNDRY_DEPLOYMENT=gpt-4o-mini
```

3. Restart — the engine auto-switches, or toggle live in the dashboard sidebar.

### Example

**Log:** `CRITICAL Database connection refused on port 5432`

| Engine | Root Cause |
|---|---|
| Rule-Based | `"Database connection pool exhausted"` |
| Foundry | `"Port 5432 refused indicates PostgreSQL crash (not overload). Likely OOM kill or full disk. Confidence 87%"` |

---

## Docker Deployment

```bash
docker-compose up --build
# API: http://localhost:5000  |  Dashboard: http://localhost:8501
```

---

## Testing

```bash
python -m pytest tests/ -v        # run all 81 tests
python -m pytest tests/test_foundry_reasoner.py -v
```

---

## Project Structure

```
ai-devops-agent/
├── app/
│   ├── __init__.py              # Flask app factory + rate limiter
│   ├── agent/
│   │   ├── observer.py          # OBSERVE  - log file reader
│   │   ├── analyzer.py          # ANALYZE  - severity & type classifier
│   │   ├── reasoner.py          # REASON   - rule-based / OpenAI RCA
│   │   ├── foundry_reasoner.py  # REASON   - Azure AI Foundry engine
│   │   ├── decision.py          # DECIDE   - action matrix
│   │   ├── actuator.py          # ACT      - remediation executor
│   │   └── reporter.py          # REPORT   - incident report generator
│   ├── api/
│   │   └── routes.py            # Flask REST endpoints
│   ├── services/
│   │   └── log_service.py       # Log file write / clear service
│   └── utils/
│       └── helpers.py           # Shared utility functions
├── ui/
│   └── dashboard.py             # Streamlit dashboard
├── tests/                       # 81 pytest tests
├── logs/app.log                  # Monitored log file
├── reports/                     # Persisted incident reports
├── config.py                    # Centralised env-var config
├── run.py                       # Flask + Gunicorn entry point
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## License

MIT - free to use, modify, and distribute.
