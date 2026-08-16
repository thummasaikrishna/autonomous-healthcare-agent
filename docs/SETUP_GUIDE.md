# Setup Guide — Running This Project in VS Code

This guide assumes you are starting from zero: nothing installed, project just unzipped. Follow it top to bottom.

---

## Part 1 — Install the Prerequisites

### 1. Install Python 3.11 or newer

- Go to https://www.python.org/downloads/
- Download the latest Python 3.11+ installer for your OS.
- **Windows:** during install, check the box "Add Python to PATH" before clicking Install.
- **Mac:** run the downloaded .pkg installer normally.
- Verify it worked — open a terminal (Windows: Command Prompt or PowerShell; Mac: Terminal) and run:

```bash
python --version
```

If that fails on Mac/Linux, try `python3 --version` instead.

### 2. Install VS Code

- Go to https://code.visualstudio.com/
- Download and install for your OS.

### 3. Install the Python extension in VS Code

- Open VS Code.
- Click the Extensions icon on the left sidebar (four squares icon).
- Search "Python" in the search box.
- Install the one published by Microsoft (top result).
- Also install "Pylance" if it isn't bundled already (usually installs automatically with Python extension).

---

## Part 2 — Open the Project

1. Unzip the project folder you received (`autonomous-healthcare-agent.zip`) anywhere on your computer, e.g. Desktop.
2. Open VS Code.
3. Click **File → Open Folder...**
4. Select the unzipped `autonomous-healthcare-agent` folder and click **Select Folder** (or **Open** on Mac).
5. VS Code will reload showing the project file tree on the left.

---

## Part 3 — Create a Virtual Environment

A virtual environment keeps this project's Python packages separate from everything else on your machine.

1. In VS Code, open a terminal: **Terminal → New Terminal** (top menu).
2. A terminal panel opens at the bottom, already inside your project folder.
3. Run:

```bash
python -m venv .venv
```

(Use `python3` instead of `python` if that's what worked in step 1 above.)

4. Wait a few seconds — this creates a `.venv` folder in your project.

5. Activate it:

**Windows (PowerShell):**
```bash
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```bash
.venv\Scripts\activate.bat
```

**Mac / Linux:**
```bash
source .venv/bin/activate
```

6. You'll know it worked because your terminal prompt now starts with `(.venv)`.

7. VS Code may pop up a notification "Select a Python Interpreter" — click it, then choose the one that shows `.venv` in its path. If no popup appears, press `Ctrl+Shift+P` (Mac: `Cmd+Shift+P`), type "Python: Select Interpreter", press Enter, and pick the `.venv` one.

---

## Part 4 — Install Dependencies

With the `(.venv)` terminal still open, run:

```bash
pip install -r requirements.txt
```

This will take a few minutes the first time — it's downloading Streamlit, ChromaDB, sentence-transformers (which includes PyTorch), and everything else. This is normal; some of these are large packages.

If you hit an error about a package failing to build, upgrade pip first and retry:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Part 5 — Configure Your Environment Variables

1. In the VS Code file explorer (left panel), find the file named `.env`.
   - If you don't see it, it may be hidden. Click the terminal and run `dir /a` (Windows) or `ls -la` (Mac/Linux) to confirm it exists. Your zip should already include a populated `.env` with your Groq and PubMed keys filled in.
   - If it's missing, copy `.env.example` and rename the copy to `.env`, then open it and fill in `LLM_API_KEY` (your Groq key) and `PUBMED_API_KEY`.
2. Open `.env` in VS Code by clicking it in the file explorer.
3. Confirm these lines have real values (not blank):

```
LLM_PROVIDER=groq
LLM_API_KEY=your-groq-key-here
PUBMED_API_KEY=your-pubmed-key-here
PUBMED_EMAIL=your-real-email@example.com
```

Set `PUBMED_EMAIL` to your actual email — NCBI requests this to identify API traffic; it does not need to be a special account, just a real address.

4. Save the file (`Ctrl+S` / `Cmd+S`).

---

## Part 6 — Run the Tests (Sanity Check)

Before running the full app, confirm everything is wired correctly:

```bash
pytest
```

You should see something like `37 passed` at the bottom, with no failures. This step doesn't need any API keys — it runs entirely on mocked data.

---

## Part 7 — Add PDFs to Index (Optional but Recommended)

1. In the file explorer, open the `data/pdfs` folder.
2. Drag and drop any clinical-trial or research PDF files into that folder (via your OS file manager — VS Code's explorer also accepts drag-and-drop directly into the folder).
3. Back in the terminal, run:

```bash
python -m app.research.document_ingestion
```

You should see log lines like `Indexed N chunks from yourfile.pdf`. If a PDF produces no output text (e.g., it's a scanned image), it will be skipped with a clear reason logged.

If you skip this step, the app still works — it will just rely on PubMed search only, since no documents will be indexed yet.

---

## Part 8 — Run the Application

In the terminal:

```bash
streamlit run app/main.py
```

- Streamlit will print a local URL, typically `http://localhost:8501`.
- It usually opens your default browser automatically. If not, hold `Ctrl` (Mac: `Cmd`) and click the link in the terminal, or copy-paste it into your browser.
- You should see the "Autonomous Healthcare Research Agent" interface load.

Try asking something like:

> What does the literature say about intermittent fasting and metabolic health?

Give it a few seconds — it's calling PubMed and Groq live.

To stop the app, click back into the terminal and press `Ctrl+C`.

---

## Part 9 — Everyday Workflow After Setup

Every time you come back to work on this project in a new terminal session:

```bash
cd path/to/autonomous-healthcare-agent
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
streamlit run app/main.py
```

You only need to repeat Part 3–4 (creating the venv, installing packages) once, unless you delete the `.venv` folder.

---

## Part 10 — Deployment (Making It Accessible Beyond Your Machine)

The simplest path is **Streamlit Community Cloud**, which is free and built exactly for this kind of app.

### Option A — Streamlit Community Cloud

1. Create a GitHub account if you don't have one: https://github.com/join
2. Create a new repository (click the **+** icon top-right on GitHub → **New repository**). Name it e.g. `autonomous-healthcare-agent`. Leave it public or private — Streamlit Cloud supports both once you connect it.
3. Push your project to that repository. In VS Code's terminal, from the project folder:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/autonomous-healthcare-agent.git
git push -u origin main
```

   Replace `YOUR-USERNAME` with your actual GitHub username. You'll be prompted to authenticate — follow GitHub's device login flow if asked.

   **Important:** your `.gitignore` already excludes `.env`, so your real API keys will NOT be pushed to GitHub. Good — never commit real keys.

4. Go to https://share.streamlit.io and sign in with GitHub.
5. Click **New app**.
6. Select your repository, branch `main`, and set the main file path to `app/main.py`.
7. Before deploying, click **Advanced settings** and paste your environment variables into the "Secrets" box in this format:

```toml
LLM_PROVIDER = "groq"
LLM_MODEL = "openai/gpt-oss-120b"
LLM_API_KEY = "your-groq-key"
PUBMED_API_KEY = "your-pubmed-key"
PUBMED_EMAIL = "your-email@example.com"
```

8. Click **Deploy**. The first build takes several minutes (installing PyTorch, etc.). Once done, you'll get a public URL like `https://your-app-name.streamlit.app`.

Notes for cloud deployment:
- The vector database (ChromaDB) and SQLite database will reset if the app restarts on a fresh container, since Streamlit Cloud's free tier doesn't guarantee persistent disk storage across redeploys. For a personal demo this is usually fine. For durable production use, point `DATABASE_URL` at a hosted Postgres/MySQL instance and use a hosted vector database instead of local ChromaDB.
- Re-run the PDF ingestion step after each fresh deploy if you want your indexed documents to persist in that session.

### Option B — Run It on Your Own Server (More Control)

If you have a VPS (e.g., a small cloud server) or a spare machine:

1. Install Python, clone your repo, follow Parts 1–7 of this guide on that machine.
2. Instead of `streamlit run app/main.py` directly, run it so it keeps running after you disconnect:

```bash
nohup streamlit run app/main.py --server.port 8501 --server.address 0.0.0.0 &
```

3. Open port 8501 in your server's firewall/security group settings.
4. Access it at `http://your-server-ip:8501`.

For anything beyond a personal demo, put it behind a reverse proxy (nginx) with HTTPS — that's a larger setup beyond this guide's scope, but straightforward to find dedicated tutorials for once you're at that stage.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Use `python3` instead, or reinstall Python and check "Add to PATH" |
| VS Code terminal doesn't show `(.venv)` prefix | Re-run the activate command from Part 3, or re-select the interpreter via `Ctrl+Shift+P` → "Python: Select Interpreter" |
| `pip install` fails on a package | Run `python -m pip install --upgrade pip` then retry |
| Streamlit opens but every answer says "DEMO MODE" | Your `LLM_API_KEY` in `.env` is empty or `DEMO_MODE=true` — check both |
| PubMed searches return nothing | Check your internet connection and that `PUBMED_EMAIL` is set; NCBI occasionally rate-limits — the app will just show "insufficient evidence" rather than crashing |
| Port 8501 already in use | Run `streamlit run app/main.py --server.port 8502` instead |
