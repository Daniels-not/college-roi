# Setup guide

Takes about 20 minutes. Commands marked **Windows** / **Mac** differ; everything else is the same.

## 0. Prerequisites

- **Python 3.10 or newer.** Check with `python --version` (Mac: `python3 --version`).
  If needed, install from <https://www.python.org/downloads/>. On Windows, tick **"Add Python to PATH"**.
- **Git** and a **GitHub** account.
- **VS Code** (recommended), with the Python and Jupyter extensions.

## 1. Unzip and open

Unzip `college-roi.zip`, then open the `college-roi` folder in VS Code
(**File → Open Folder**) and open a terminal (**Terminal → New Terminal**).

## 2. Virtual environment

```bash
python -m venv .venv
```

Activate it (do this every time you open a new terminal):

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
  If it's blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.
- **Mac/Linux:** `source .venv/bin/activate`

You should see `(.venv)` at the start of the prompt.

## 3. Install

```bash
pip install -e ".[dev,analysis]"
```

This installs the pipeline plus dbt, statsmodels, scikit-learn, Streamlit and Jupyter (a few minutes).

## 4. Try it on demo data (no API key needed)

```bash
python -m scorecard demo
streamlit run app/streamlit_app.py
```

The dashboard opens at <http://localhost:8501> with a yellow **Demo mode** banner. Those
schools are fake; this step just proves everything works on your machine. Stop the app with
**Ctrl+C**. Demo output lives in `data/demo/` and never mixes with real data.

Then run the tests:

```bash
pytest
```

Expect `22 passed`.

## 5. Get your API key

1. Sign up at <https://api.data.gov/signup/>. The key arrives by email in about a minute.
2. Copy the example env file:
   - **Windows:** `copy .env.example .env`
   - **Mac:** `cp .env.example .env`
3. Open `.env` and replace `your_key_here` with your key. `.env` is git-ignored, so the key stays private.

## 6. Run on real data

```bash
python -m scorecard check-fields
```

This makes one API call and lists every field with the percent of schools that have it filled in.
**Any field at 0% has a wrong name.** Send me that output and I'll fix it in `src/scorecard/config.py`.

Then run everything:

```bash
python -m scorecard all
```

That's about 45 API calls plus dbt, the models, and the exports (a few minutes). It ends with a
summary: data quality, HBCU comparison, model fit and the top 10 by value added.

```bash
streamlit run app/streamlit_app.py
```

The demo banner is gone; this is real data.

## 7. Explore in the notebook

Open `notebooks/analysis.ipynb` in VS Code, pick the `.venv` kernel (top right), and **Run All**.
Section 6 is where you write your findings. Copy the best 3 into the README.

## 8. Put it on GitHub

Create an **empty** repo named `college-roi` on GitHub (no README, no .gitignore), then:

```bash
git init
git add .
git commit -m "College ROI analysis: pipeline, dbt, models, dashboard"
git branch -M main
git remote add origin https://github.com/Daniels-not/college-roi.git
git push -u origin main
```

`exports/` is committed on purpose: the deployed dashboard reads it. `data/` and `.env` are not.

## 9. Turn on GitHub Actions

- **CI** runs automatically on every push (Actions tab). The README badge turns green when it passes.
- **Monthly refresh** needs your key as a secret: repo **Settings → Secrets and variables → Actions →
  New repository secret**, name `SCORECARD_API_KEY`, value = your key.
  Test it with **Actions → Monthly data refresh → Run workflow**.

## 10. Deploy the dashboard (free)

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub**.
3. Repository `Daniels-not/college-roi`, branch `main`, main file `app/streamlit_app.py`.
4. Deploy. Streamlit installs `app/requirements.txt` automatically.
5. Paste the URL at the top of the README.

Each monthly refresh commits new exports and the app updates on its own.

## 11. Tableau version (optional, recommended for analyst roles)

Follow `docs/tableau.md`. It uses the CSVs in `exports/tableau/`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found (Windows) | Reinstall Python with "Add to PATH", or use `py` instead of `python` |
| `dbt not found` | Activate `.venv` and re-run `pip install -e ".[dev,analysis]"` |
| `HTTP 403` / `Missing API key` | Check that `.env` exists in the project root and the key has no quotes or spaces |
| `HTTP 429` | Rate limit hit; the client retries automatically. With `DEMO_KEY`, add `--max-pages 2` |
| A dbt test fails | The data broke a rule (e.g. a rate outside 0–1). The output names the test; send it to me |
| Dashboard says "No data found" | Run `python -m scorecard all` (or `demo`) first |
| Map is blank | The map outline loads from Plotly's CDN; check your internet connection |
