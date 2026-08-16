# Streamlit Community Cloud deployment notes
#
# 1. Push this repo to GitHub.
# 2. Go to https://share.streamlit.io and click "New app".
# 3. Select this repository, branch `main`, and Main file path: `app/main.py`.
# 4. In App settings → Secrets, paste values from `.streamlit/secrets.toml.example`
#    (with your real LLM_API_KEY and PUBMED_EMAIL).
# 5. Deploy.
#
# Notes:
# - Uses Python 3.12 (`runtime.txt`).
# - First boot downloads the embedding model and can take several minutes.
# - Free Cloud apps have limited RAM; Chroma + sentence-transformers may hit
#   memory limits. If the app is killed, upgrade the Cloud resource or slim deps.
