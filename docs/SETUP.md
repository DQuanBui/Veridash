# Setup Guide

Everything you need to run, test, configure and deploy Veridash.

- [Prerequisites](#prerequisites)
- [Local quickstart](#local-quickstart)
- [Configuration and secrets](#configuration-and-secrets)
- [Running tests](#running-tests)
- [Deploying to Streamlit Community Cloud](#deploying-to-streamlit-community-cloud)
- [Troubleshooting](#troubleshooting)

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11 or newer | Developed and tested on Python 3.13. Check with `python --version` (Windows) or `python3 --version` (macOS). |
| Git | To clone the repository. |
| A Gemini API key (optional) | Only needed for AI insights and plain-English questions. Get one free at [Google AI Studio](https://aistudio.google.com/apikey). |

## Local quickstart

### Windows (PowerShell)

```powershell
git clone https://github.com/DQuanBui/Veridash.git
cd Veridash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
streamlit run app.py
```

If PowerShell blocks the activation script, allow local scripts for your user once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### macOS (Terminal)

```bash
git clone https://github.com/DQuanBui/Veridash.git
cd Veridash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
streamlit run app.py
```

The app opens at http://localhost:8501. `requirements.txt` holds the runtime dependencies (what the cloud
deployment installs); `requirements-dev.txt` adds pytest and Ruff for development.

## Configuration and secrets

Veridash works fully without any configuration. To enable AI features, provide a Gemini key in one of three ways
(checked in this order):

1. **Sidebar field (per session).** Paste a key into "Bring your own Gemini key" on the Analyze page. It is held
   only in that browser session's memory.
2. **Streamlit secrets (recommended for local and cloud).** Copy the example file and add your key:

   ```powershell
   Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml   # Windows
   ```
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml          # macOS
   ```

   Then edit `.streamlit/secrets.toml`:

   ```toml
   GEMINI_API_KEY = "your-gemini-api-key"
   # Optional: choose a different model
   # GEMINI_MODEL = "gemini-3.6-flash"
   ```

   `secrets.toml` is listed in `.gitignore` and must never be committed.
3. **Environment variable.** `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) are also read from the environment.

### Choosing a model

The default model is `gemini-3.6-flash`, a stable Flash model with a free tier at the time of writing. Model
names change; check the current list at <https://ai.google.dev/gemini-api/docs/models> and set `GEMINI_MODEL` to
switch (for example to `gemini-3.8-flash` or `gemini-3.5-flash-lite`).

### Other settings

| Setting | Where | Default |
|---|---|---|
| Theme colors and font | `.streamlit/config.toml` | Teal on white, Inter |
| Upload size limit | `.streamlit/config.toml` (`maxUploadSize`) and `core/settings.py` (`MAX_FILE_MB`) | 50 MB |
| Row and column limits, sampling threshold, query timeout | `core/settings.py` | 1,000,000 rows, 300 columns, 200,000 rows, 10 s |
| AI calls per session | `core/settings.py` (`MAX_AI_CALLS_PER_SESSION`) | 10 |
| Health score weights | `core/health.py` (`HEALTH_WEIGHTS`) | See the Guide page |
| Author name, email and LinkedIn URL | `core/settings.py` | Edit `LINKEDIN_URL` to your profile |

## Running tests

```bash
pytest            # all tests, including Streamlit AppTest smoke tests (about 20 seconds)
ruff check .      # lint
```

To regenerate the example datasets (seeded, so the output is identical every time):

```bash
python -m data.samples.generate_samples
```

## Deploying to Streamlit Community Cloud

1. **Push the repository to GitHub.** The repository must contain `app.py`, `requirements.txt` and the `.streamlit`
   folder (without `secrets.toml`).
2. **Sign in** at <https://share.streamlit.io> with your GitHub account and authorise access to the repository.
3. Click **Create app**, then choose **Deploy a public app from GitHub**.
4. Fill in the form:
   - **Repository:** `DQuanBui/Veridash`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL (optional):** choose a subdomain such as `veridash`, which gives `https://veridash.streamlit.app`.
5. Open **Advanced settings**:
   - **Python version:** 3.12 or 3.13.
   - **Secrets:** paste the same TOML you use locally:

     ```toml
     GEMINI_API_KEY = "your-gemini-api-key"
     GEMINI_MODEL = "gemini-3.6-flash"
     ```

     Leave the box empty to run the app without AI features. Visitors can still paste their own key.
6. Click **Deploy**. The first build takes a few minutes while dependencies install.
7. **Update the README** live demo link to your app URL.

To change secrets later, open the app's **Settings > Secrets** on share.streamlit.io; the app restarts with the
new values. Every push to `main` redeploys automatically.

> A key stored in Cloud secrets is shared by every visitor, and each session can make up to 10 AI calls. On the
> free tier Google's limits apply across all visitors, so consider leaving the shared key out and letting
> visitors bring their own.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `streamlit` is not recognised | Activate the virtual environment first (see the quickstart). |
| PowerShell refuses to run `Activate.ps1` | Run the `Set-ExecutionPolicy` command above, then reopen PowerShell. |
| Port 8501 is already in use | `streamlit run app.py --server.port 8502` |
| "The Gemini API key was rejected" | Check the key in Google AI Studio and that it has no extra spaces or quotes. |
| "The configured Gemini model was not found" | The model was renamed or retired. Set `GEMINI_MODEL` to a current model name. |
| "Gemini's rate limit or quota was reached" | Wait a minute, or use a key with higher limits. Rule-based insights keep working. |
| "This session has used its 10 AI calls" | Reload the page to start a new session, or raise `MAX_AI_CALLS_PER_SESSION`. |
| A number column shows as text | More than 10% of its values are not numbers. Clean stray text such as "N/A" or "TBD". |
| Dates are read in the wrong order | Ambiguous dates are read month first. Use ISO dates (2024-03-31) where possible. |
| `.xls` files fail to open | Make sure `xlrd` is installed (`pip install -r requirements.txt`). |
| Old results after editing code | Press `C` in the app (or use the menu) to clear the cache, then rerun. |
