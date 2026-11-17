# Deploying DA Sumit to Streamlit Community Cloud

This gives you a permanent URL like **https://da-sumit.streamlit.app** that works
from any device, anytime — no laptop or terminal needed.

You need: a **GitHub account** and an **OpenAI API key**.

---

## Step 1 — Create a GitHub repository

1. Go to <https://github.com/new>
2. **Repository name:** `da-sumit`
3. Choose **Private** (recommended) or Public.
4. Leave "Add a README file" **unchecked**.
5. Click **Create repository**.

---

## Step 2 — Upload the files

The folder **`deploy`** in this project contains exactly the files needed.

1. Open the `deploy` folder in File Explorer.
2. On your new GitHub repo page, click **Add file → Upload files**.
3. Select **everything inside `deploy`** (the `app.py`, `requirements.txt`,
   `.gitignore`, `sumit07` folder, `.streamlit` folder, `data` folder) and drag
   it onto the page.
   - If your browser won't accept folders, upload `app.py` + `requirements.txt`
     first, then use **Add file → Upload files** again for each folder.
4. Click **Commit changes**.

Your repo should now show `app.py`, `requirements.txt`, `sumit07/`,
`.streamlit/`, and `data/` at the top level.

---

## Step 3 — Deploy on Streamlit Community Cloud

1. Go to <https://share.streamlit.io>
2. Click **Sign in with GitHub** and authorize Streamlit.
3. Click **Create app** (or **New app**).
4. Fill in:
   - **Repository:** `<your-username>/da-sumit`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** you can set the subdomain, e.g. `da-sumit`
5. Click **Deploy**.

First build takes ~2–3 minutes.

---

## Step 4 — Add your secrets (API key + password)

Your OpenAI key must **not** be in the code. Add it as a secret:

1. In the Streamlit app dashboard, open **Settings → Secrets**.
2. Paste this (with your real values):

```toml
OPENAI_API_KEY = "sk-proj-...your-key..."
APP_PASSWORD = "choose-a-strong-password"
```

3. Click **Save**. The app restarts automatically.

- `OPENAI_API_KEY` — the app picks it up automatically, no pasting in the sidebar.
- `APP_PASSWORD` — **important**: this puts a password gate in front of the app so
  random visitors can't use your key and spend your credits. Without it the app
  is open to anyone with the link.

---

## Step 5 — Open your site

Your permanent URL is:

```
https://<the-subdomain-you-chose>.streamlit.app
```

You can bookmark it on any device. If the app has been idle, the first load may
take ~20–30 seconds while it wakes up.

To change the URL later: app dashboard → **Settings → General → App URL**.

---

## Updating the app later

- **Easiest:** edit files directly on GitHub (or re-upload), then the app
  redeploys automatically.
- Or edit locally and re-upload the changed files.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build failed | Dashboard → **Logs** → read the error; usually a missing file in `requirements.txt` |
| `ModuleNotFoundError: sumit07` | Make sure the `sumit07/` folder was uploaded at the repo root |
| `401 Incorrect API key` | Fix the key in **Settings → Secrets** |
| `429 insufficient_quota` | Add credit to your OpenAI account |
| No charts / exports | The cloud filesystem is temporary; downloads must be done in the same session |
| App is public and you didn't set a password | Add `APP_PASSWORD` in Secrets immediately |
