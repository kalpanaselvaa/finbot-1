# Deploying FinBot to Azure

FinBot has two parts that each get their own Azure service:

| Component | Azure Service | Notes |
|---|---|---|
| **FastAPI backend** (`app/`) | Azure App Service (Linux) | Runs uvicorn, hosts `/health` and `/brief` |
| **Next.js frontend** (`frontend/`) | Azure Static Web Apps | Hybrid SSR mode, free tier available |

---

## Prerequisites

- [Azure CLI installed](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (`winget install Microsoft.AzureCLI`)
- An Azure account ([free tier available](https://azure.microsoft.com/free))
- Your project pushed to a **GitHub** repo (required for the SWA frontend flow)

> [!IMPORTANT]
> Your `.env` file must **never** be committed. Secrets are injected via Azure App Settings / GitHub Secrets instead.

---

## Part 1 — Backend: FastAPI on Azure App Service

### Step 1 — Prep: Add a `requirements.txt`

Azure App Service auto-installs from `requirements.txt`. Since you use `uv`, generate it once:

```powershell
# Run from d:\projects\Courses\Bootcamps\finbot
uv pip compile pyproject.toml -o requirements.txt
```

Also confirm `run.py` starts uvicorn correctly (Azure uses this as the startup command):

```python
# run.py — should already look like this
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
```

### Step 2 — Fix CORS for Production

Update `main.py` to allow both localhost (dev) and your future SWA domain (prod):

```python
# app/main.py
allow_origins=[
    "http://localhost:3000",
    "https://fin-bot-api.azurewebsites.net",  # add after SWA is created
]
```

### Step 3 — Log in and Deploy with `az webapp up`

```sh
az login

# Run from the repo root (d:\projects\Courses\Bootcamps\finbot)
# az webapp up --name fin-bot-api --runtime "PYTHON:3.13" --sku F1 --logs
az webapp up \
  --name fin-bot-api \
  --runtime "PYTHON:3.13" \
  --sku F1 \
  --logs
```

> [!NOTE]
> This single command creates a **Resource Group**, **App Service Plan**, and **Web App**, then ZIPs and deploys your code. The app URL printed at the end is your backend URL.

`--sku B1` costs ~$13/month. Use `--sku F1` for a free tier (limited — no custom domains, shared CPU).

### Step 4 — Set the Startup Command

Azure needs to know how to start a FastAPI app. Set this via the CLI:

```sh
az webapp config set \
  --name fin-bot-api \
  --resource-group  kalpanaselvaa_rg_0160 \
  --startup-file "python run.py"
```

Or if you don't have `run.py`, use:
```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```
(add `gunicorn` to `requirements.txt` first.)

### Step 5 — Set Environment Variables (App Settings)

Never commit your `.env`. Instead, push each variable as an Azure App Setting:

```sh
export RG=$(az webapp show --name fin-bot-api --query resourceGroup -o tsv)

az webapp config appsettings set \
  --name fin-bot-api \
  --resource-group $RG \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com" \
    AZURE_OPENAI_API_KEY="<your-api-key>" \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o" \
    AZURE_OPENAI_API_VERSION="2024-08-01-preview" \
    AZURE_AI_PROJECT_ENDPOINT="https://<your-resource>.services.ai.azure.com/api/projects/<your-project>" \
    SERPAPI_API_KEY="<your-serpapi-key>" \
    SQLITE_DB_PATH="/tmp/finance_agent.db"
```

> [!WARNING]
> **SQLite on App Service is ephemeral.** The filesystem resets on every deployment/restart. For production, migrate to **Azure SQL** or **Azure Cosmos DB**. For a bootcamp project, SQLite is fine but data won't persist across deployments.

### Step 6 — Enable LangSmith (optional)

Add any LangSmith variables the same way:

```powershell
az webapp config appsettings set `
  --name finbot-api `
  --resource-group <resource-group> `
  --settings `
    LANGSMITH_API_KEY="your-langsmith-key" `
    LANGCHAIN_TRACING_V2="true"
```

### Step 7 — Verify the Backend

```powershell
# Should return {"status":"ok"}
curl https://finbot-api.azurewebsites.net/health
```

---

## Part 2 — Frontend: Next.js on Azure Static Web Apps

### Step 1 — Point the `NEXT_PUBLIC_API_URL` at your backend

In `frontend/.env.local` (for local dev) and as a GitHub Secret (for prod):

```
NEXT_PUBLIC_API_URL=https://finbot-api.azurewebsites.net
```

Make sure your frontend uses this env var when calling the backend instead of a hardcoded URL.

### Step 2 — Enable Next.js Standalone output (recommended)

Azure SWA has a 250 MB app limit. Enable standalone to reduce bundle size.

```ts
// frontend/next.config.ts
const nextConfig = {
  output: "standalone",
};
export default nextConfig;
```

Then update the build script in `frontend/package.json`:

```json
"scripts": {
  "build": "next build && cp -r .next/static .next/standalone/.next/ && cp -r public .next/standalone/"
}
```

> [!NOTE]
> The `cp` command above is for Linux/macOS (used in CI). The Azure GitHub Action runs on Ubuntu, so this works fine in CI even though you're on Windows locally.

### Step 3 — Deploy via Azure Portal (connect to GitHub)

1. Go to [portal.azure.com](https://portal.azure.com) → **Create a resource** → search **Static Web Apps** → **Create**
2. Fill in:
   - **Subscription / Resource Group**: use same group as backend
   - **Name**: `finbot-app`
   - **Plan**: Free
   - **Region**: closest to you
3. Under **Deployment details**, select **GitHub** → authorize → pick your repo and branch
4. Under **Build details**:
   - **Build Preset**: `Next.js`
   - **App location**: `/frontend`
   - **Api location**: *(leave empty)*
   - **Output location**: *(leave empty)*
5. Click **Review + Create** → **Create**

Azure automatically creates a **GitHub Actions workflow** file in your repo (`.github/workflows/azure-static-web-apps-*.yml`).

### Step 4 — Add Environment Variables to GitHub Actions

Since Next.js bakes some env vars at build time, add them as GitHub Secrets:

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
2. Add: `NEXT_PUBLIC_API_URL` = `https://finbot-api.azurewebsites.net`

Then edit the generated workflow file to pass it during build:

```yaml
# .github/workflows/azure-static-web-apps-*.yml
- name: Build And Deploy
  uses: Azure/static-web-apps-deploy@v1
  with:
    azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
    repo_token: ${{ secrets.GITHUB_TOKEN }}
    action: "upload"
    app_location: "/frontend"
    output_location: ""
  env:
    NEXT_PUBLIC_API_URL: ${{ secrets.NEXT_PUBLIC_API_URL }}
```

### Step 5 — Update Backend CORS

Once you have your SWA URL (e.g. `https://finbot-app.azurestaticapps.net`), go back and update `main.py` CORS and redeploy:

```powershell
# Redeploy backend after CORS change
az webapp up --name finbot-api
```

### Step 6 — Verify Full Flow

1. Visit `https://finbot-app.azurestaticapps.net`
2. Submit a query in the chat
3. It should call `https://finbot-api.azurewebsites.net/brief` and get a response

---

## Summary of Azure Resources

| Resource | Name | Cost |
|---|---|---|
| App Service Plan (B1) | finbot-api-plan | ~$13/mo |
| App Service (Web App) | finbot-api | included |
| Static Web App | finbot-app | Free |

> [!TIP]
> To tear everything down: `az group delete --name <resource-group> --yes`

---

## Quick Reference: Re-deploy After Changes

```powershell
# Backend: re-deploy after any Python changes
az webapp up --name finbot-api

# Frontend: just push to GitHub — Actions re-deploys automatically
git push origin main
```

---

## Reference Docs

- [Azure App Service: Deploy Python (FastAPI)](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
- [Azure Static Web Apps: Deploy Next.js hybrid](https://learn.microsoft.com/en-us/azure/static-web-apps/deploy-nextjs-hybrid)
- [Azure App Service: Configure app settings](https://learn.microsoft.com/en-us/azure/app-service/configure-common)
