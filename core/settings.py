"""Central configuration constants for Veridash.

Keeping limits and identity values in one place makes the app easy to tune and
keeps the UI text (Guide, About) in sync with the behaviour of the code.
"""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Veridash"
TAGLINE = "Drop your data. Trust every number."
SUBHEAD = (
    "Upload a CSV or Excel file and get a health check, charts, insights and exports "
    "in seconds, with every number traced back to the query that produced it."
)

# Author / contact (replace LINKEDIN_URL with your profile)
AUTHOR_NAME = "Quan Bui"
AUTHOR_ROLE = "Information Systems @ Fordham University"
AUTHOR_EMAIL = "dbui10@fordham.edu"
LINKEDIN_URL = "https://www.linkedin.com/in/your-profile"
GITHUB_URL = "https://github.com/DQuanBui/Veridash"

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "data" / "samples"
ASSETS_DIR = ROOT_DIR / "assets"

# Input limits
MAX_FILE_MB = 50
MAX_ROWS = 1_000_000
MAX_COLUMNS = 300

# Above this many rows, heavy visuals (scatter, distributions, preview) use a
# reproducible sample. KPIs and aggregates always use the full data.
HEAVY_VISUAL_ROW_LIMIT = 200_000
SCATTER_MAX_POINTS = 5_000

# Query limits
QUERY_TIMEOUT_S = 10.0
ASK_MAX_ROWS = 1_000

# AI
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
MAX_AI_CALLS_PER_SESSION = 10
AI_TIMEOUT_S = 45
CATEGORY_LABELS_FOR_AI = 10

# Cache lifetime for analysis results held in server memory
CACHE_TTL_S = 3600
