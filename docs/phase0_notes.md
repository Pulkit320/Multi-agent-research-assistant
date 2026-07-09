# Phase 0: Project Scaffolding & Connections

## What We Built

We created a monorepo setup to lay the plumbing for the Multi-Agent Research Assistant:
1. **Backend**: A modular FastAPI setup inside the `backend/` directory.
   - Initialized configuration management utilizing `pydantic-settings` to dynamically load environment variables.
   - Built a `/health` endpoint to support verification and future health probes.
   - Structured directories for `core/` logic, API `routers/`, and future `agents/`.
2. **Frontend**: A React client bootstrapped via Vite and styled with Tailwind CSS v4.
   - Developed a responsive, premium dark mode status dashboard that queries the backend `/health` endpoint.
3. **Documentation**: Scaffolding guidelines and architectural notes.

---

## Git & GitHub Setup Instructions

To ensure secrets and virtual environments (like `.env` and `.venv/`) are not tracked by version control, follow these steps to set up `.gitignore` and push the project.

### 1. Create `.gitignore` in the project root
Create a `.gitignore` file in the monorepo root and add the following lines:
```text
# Python virtual environments & caches
__pycache__/
*.py[cod]
.venv/
venv/
.env

# Node dependencies and build files
node_modules/
dist/
.env.local
npm-debug.log*

# System files
.DS_Store
```

### 2. Initialize and Push to GitHub
Execute these commands in the terminal from the root folder:
```bash
# Initialize git repository
git init

# Stage files
git add .

# Commit
git commit -m "chore: initial commit - setup monorepo scaffold"

# Link and push to your GitHub repository:
# git remote add origin https://github.com/username/repository.git
# git branch -M main
# git push -u origin main
```

---

## Why It's Structured This Way

Even though the code footprint is currently very minimal, we intentionally separated the codebase into `agents/`, `routers/`, and `core/` sub-folders. This early structural split serves key design principles:

### 1. Separation of Concerns (SoC)
- **`core/`**: Holds configuration loading (`config.py`), global system settings, databases, or third-party client instantiations. This layer does not care about HTTP request handling (routers) or agent control flow. Keeping it separate prevents circular imports and hardcoded settings.
- **`routers/`**: Handles HTTP networking (request parsing, response formatting, status codes, CORS configuration, routing). It isolates the protocol layer (FastAPI) from business logic.
- **`agents/`**: Contains the pure algorithmic and LLM orchestrations (agent classes, memory patterns, tool execution loops). It should ideally remain protocol-agnostic. Agents can be imported and executed inside router endpoints, CLI scripts, or offline batch processes without depending on a running FastAPI application.

### 2. Scalability & Development Velocity
- As the project grows, we will introduce multiple endpoints (e.g., `/run_research`, `/agent_feedback`, `/history`). Plunging all code into `main.py` creates a monolithic bottleneck that is difficult to maintain.
- Creating folders early establishes clear patterns for new developers. They immediately know where to place a new agent, a new endpoint, or a configuration variable without having to reorganize the repository later.

---

## In My Own Words
- This phase is about setting up the skeleton of our research assistant. We are creating the basic folder structure and putting it on github. This is an important step because it will help us to keep our code organized and easy to maintain.

---

## Questions I Still Have


