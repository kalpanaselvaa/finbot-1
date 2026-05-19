# Azure App Service Deployment — Troubleshooting Guide

All issues below were encountered deploying a FastAPI + LangGraph + Azure AI Foundry app to Azure App Service (Python 3.13, F1 SKU).

---

## Issue 1 — Site failed to start within 10 minutes

### Symptom
```
Status: Site failed to start. Time: 750(s)
Error: Deployment for site 'fin-bot-api' ... failed because the worker process failed to start within the allotted time.
```

### Root Cause
`app/agent.py` ran expensive initialisation code at **module import time**:
- `AzureChatOpenAI(...)` validated credentials on construction
- `AgentServiceFactory(...)` instantiated `DefaultAzureCredential()`, which probed many identity sources (each with a network timeout)
- `factory.create_prompt_agent(...)` made an **HTTP call to Azure AI Foundry** before any environment variables were available

When Gunicorn imported the module to boot a worker, all of this ran synchronously. The worker timed out before it ever bound to a port.

### Resolution
Move all initialisation into a lazy function called only on the first request:

```python
# app/agent.py
_agent = None

def _get_agent():
    global _agent
    if _agent is not None:
        return _agent
    # initialise LLM, factory, agent here ...
    _agent = factory.create_prompt_agent(...)
    return _agent

def run_agent(query, thread_id):
    agent = _get_agent()
    ...
```

Nothing runs at import time. The app starts instantly; credentials are validated only when the first real request arrives.

---

## Issue 2 — Deployment rejected with HTTP 403

### Symptom
```
Deployment endpoint responded with status code 403
Error: This web app is stopped.
```

### Root Cause
A previous failed deployment left the App Service in a **stopped** state. Azure's Kudu (SCM) deployment endpoint rejects zip deployments while the site is stopped.

### Resolution
Start the app before deploying:

```bash
RG=$(az webapp show --name fin-bot-api --query resourceGroup -o tsv)
az webapp start --name fin-bot-api --resource-group $RG

# Then redeploy
az webapp up --name fin-bot-api --runtime "PYTHON:3.13" --sku F1 --logs
```

---

## Issue 3 — Oryx auto-detects Flask; uses Gunicorn sync worker

### Symptom
Log output:
```
App Command Line not configured, will attempt auto-detect
Detected an app based on Flask
Generating `gunicorn` command for 'run:app'
TypeError: FastAPI.__call__() missing 1 required positional argument: 'send'
```

### Root Cause
Two sub-problems:

1. **No startup command was registered.** `az webapp up` does not accept `--startup-file`; the flag is set separately via `az webapp config set`.
2. **FastAPI is ASGI; Gunicorn's default sync worker is WSGI.** When Oryx auto-detected the app, it generated a plain `gunicorn` command. FastAPI's `__call__` requires three arguments (`scope`, `receive`, `send`) — the ASGI signature — but the sync worker called it with two (the WSGI signature), raising `TypeError`.

### Resolution

**Step 1.** Create `startup.sh` in the repo root:

```bash
#!/bin/bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Step 2.** Register it as the startup command after deploying:

```bash
RG=$(az webapp show --name fin-bot-api --query resourceGroup -o tsv)

az webapp config set \
  --name fin-bot-api \
  --resource-group $RG \
  --startup-file "startup.sh"

az webapp restart --name fin-bot-api --resource-group $RG
```

> `az webapp up` deploys the file but does **not** register it automatically. The `config set` step is always required.

---

## Issue 4 — Missing OpenAI credentials at runtime

### Symptom
```
openai.OpenAIError: Missing credentials. Please pass one of `api_key`,
`azure_ad_token`, `azure_ad_token_provider`, or the `AZURE_OPENAI_API_KEY`
or `AZURE_OPENAI_AD_TOKEN` environment variables.
```

### Root Cause
The `.env` file is listed in `.gitignore` and was never included in the zip deployment. Azure App Service has no knowledge of local environment files.

### Resolution
Inject each variable as an **App Service Application Setting** (these become environment variables inside the container):

```bash
RG=$(az webapp show --name fin-bot-api --query resourceGroup -o tsv)

az webapp config appsettings set \
  --name fin-bot-api \
  --resource-group $RG \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com" \
    AZURE_OPENAI_API_KEY="<your-key>" \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o" \
    AZURE_OPENAI_API_VERSION="2024-08-01-preview" \
    AZURE_AI_PROJECT_ENDPOINT="https://<your-resource>.services.ai.azure.com/api/projects/<project>" \
    SERPAPI_API_KEY="<your-key>"
```

App Service restarts automatically after `appsettings set`.

> **Security best practice:** Use [Key Vault references](https://learn.microsoft.com/en-us/azure/app-service/app-service-key-vault-references) instead of plain-text values:
> `AZURE_OPENAI_API_KEY="@Microsoft.KeyVault(SecretUri=https://<kv>.vault.azure.net/secrets/<name>/)"`

---

## Issue 5 — DefaultAzureCredential fails for Azure AI Foundry

### Symptom
```
azure.core.exceptions.ClientAuthenticationError: DefaultAzureCredential failed to retrieve a token.
  EnvironmentCredential: Environment variables are not fully configured.
  ManagedIdentityCredential: No response from the IMDS endpoint.
  AzureCliCredential: Azure CLI not found on path
  ...
```

### Root Cause
`AgentServiceFactory` authenticates against Azure AI Foundry using `DefaultAzureCredential()`. On App Service, `DefaultAzureCredential` tries these sources in order:

| Credential | Why it failed |
|---|---|
| `EnvironmentCredential` | `AZURE_CLIENT_ID/SECRET/TENANT_ID` not set |
| `WorkloadIdentityCredential` | Not a Kubernetes environment |
| `ManagedIdentityCredential` | System-assigned identity not enabled on the App Service |
| `AzureCliCredential` | Azure CLI not installed in the container |
| Others | Not applicable in a containerised App Service |

### Resolution (Recommended — Managed Identity, no secrets)

**Step 1.** Enable system-assigned managed identity on the App Service:

```bash
RG=$(az webapp show --name fin-bot-api --query resourceGroup -o tsv)
az webapp identity assign --name fin-bot-api --resource-group $RG
```

**Step 2.** Retrieve the identity's principal ID:

```bash
PRINCIPAL_ID=$(az webapp identity show \
  --name fin-bot-api \
  --resource-group $RG \
  --query principalId -o tsv)
```

**Step 3.** Grant it the **Azure AI Developer** role on your AI Foundry project:

```bash
az role assignment create \
  --role "Azure AI Developer" \
  --assignee $PRINCIPAL_ID \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<resource>/projects/<project>"
```

**Step 4.** Restart the app:

```bash
az webapp restart --name fin-bot-api --resource-group $RG
```

`DefaultAzureCredential` will now automatically use the managed identity — no credentials to rotate or store.

### Alternative — Service Principal (if managed identity is not preferred)

Add three app settings; `EnvironmentCredential` picks them up automatically:

```bash
az webapp config appsettings set \
  --name fin-bot-api \
  --resource-group $RG \
  --settings \
    AZURE_CLIENT_ID="<sp-app-id>" \
    AZURE_CLIENT_SECRET="<sp-secret>" \
    AZURE_TENANT_ID="<tenant-id>"
```

---

## Issue 6 — `PermissionDenied: agents/write` despite valid managed identity

### Symptom
```
azure.core.exceptions.ClientAuthenticationError: (PermissionDenied)
The principal `<id>` lacks the required data action
`Microsoft.CognitiveServices/accounts/AIServices/agents/write`
to perform `POST /api/projects/{projectName}/agents/*` operation.
```

### Root Cause
Two compounding sub-problems:

**Sub-problem A — Wrong scope for the role assignment.**
The `Azure AI Developer` role was initially assigned at the *project* scope:
```
.../Microsoft.CognitiveServices/accounts/<resource>/projects/<project>
```
The `agents/write` data action is enforced at the *account* (parent) scope. Assigning at the project level does not grant it.

**Sub-problem B — `Azure AI Developer` does not cover `AIServices` data actions.**
Inspecting the role definition reveals its data actions are:
```
Microsoft.CognitiveServices/accounts/OpenAI/*
Microsoft.CognitiveServices/accounts/SpeechServices/*
Microsoft.CognitiveServices/accounts/ContentSafety/*
Microsoft.CognitiveServices/accounts/MaaS/*
```
The new Azure AI Services / AI Foundry Agents API runs under `AIServices/*`, which is **not included**. `Azure AI Developer` is therefore insufficient for agent creation on a unified AI Services resource.

You can verify a role's data actions with:
```bash
az role definition list --name "Azure AI Developer" \
  --query "[0].permissions[0].dataActions" -o json
```

### Resolution
Assign **`Cognitive Services User`** at the account scope instead. Its single wildcard data action `Microsoft.CognitiveServices/*` covers all sub-namespaces including `AIServices/agents/write`:

```bash
PRINCIPAL_ID=$(az webapp identity show \
  --name fin-bot-api --resource-group $RG --query principalId -o tsv)

az role assignment create \
  --role "Cognitive Services User" \
  --assignee $PRINCIPAL_ID \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<resource>"
```

> **Note:** Data-plane RBAC for Cognitive Services can take **3–10 minutes** to propagate after assignment. Wait before testing, and restart the app after waiting.

---

## Issue 7 — `AzureChatOpenAI` returns 404 on new Azure AI Services resources

### Symptom
```
openai.NotFoundError: Error code: 404 - {'error': {'code': '404', 'message': 'Resource not found'}}
```

The error occurs when calling the `/brief` endpoint even though the Azure OpenAI resource and deployment exist.

### Root Cause
This is the most architecturally subtle issue encountered. There are two variants:

**Variant A — Trailing path in `AZURE_OPENAI_ENDPOINT`.**
The endpoint was set to `https://<resource>.openai.azure.com/openai/v1` (with the path suffix).
`AzureChatOpenAI` appends its own path on top of this, producing a malformed URL:
```
https://<resource>.openai.azure.com/openai/v1/openai/deployments/<name>/chat/completions
```

**Variant B — Wrong LangChain class for the resource type (root cause).**
Newer Azure AI Foundry resources are provisioned as **Azure AI Services** (`Microsoft.CognitiveServices/accounts` of kind `AIServices`), not as classic Azure OpenAI resources. They use a fundamentally different URL scheme:

| Resource type | URL pattern |
|---|---|
| Classic Azure OpenAI | `.../openai/deployments/<name>/chat/completions?api-version=...` |
| Azure AI Services (new) | `.../openai/v1/chat/completions` (model in request body, no deployment in URL) |

`AzureChatOpenAI` from `langchain_openai` always constructs the *classic* URL pattern.
When used against a new AI Services resource it produces 404s because the deployment-in-URL path does not exist.

You can identify your resource type:
```bash
az cognitiveservices account show \
  --name <resource> --resource-group <rg> --query kind -o tsv
# Returns "OpenAI" (classic) or "AIServices" (new)
```

### Resolution
Replace `AzureChatOpenAI` with `AzureAIOpenAIApiChatModel` from `langchain_azure_ai`, which is purpose-built for the new AI Services endpoint. It auto-configures the correct client via the project endpoint and `DefaultAzureCredential` (managed identity):

```python
# app/agent.py — replace this:
from langchain_openai import AzureChatOpenAI
llm = AzureChatOpenAI(
    azure_endpoint=settings.azure_openai_endpoint,
    api_key=settings.azure_openai_api_key,
    azure_deployment=settings.azure_openai_deployment,
    api_version=settings.azure_openai_api_version,
    temperature=0,
)

# with this:
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from azure.identity import DefaultAzureCredential

llm = AzureAIOpenAIApiChatModel(
    project_endpoint=settings.azure_ai_project_endpoint,  # AZURE_AI_PROJECT_ENDPOINT
    credential=DefaultAzureCredential(),
    model=settings.azure_openai_deployment,
    use_responses_api=False,  # use standard chat completions for tool compatibility
    max_retries=2,
)
```

Key differences:
- Uses `project_endpoint` (the `AZURE_AI_PROJECT_ENDPOINT`) — no separate `AZURE_OPENAI_ENDPOINT` needed
- Authenticates via `DefaultAzureCredential` (managed identity) — no API key required
- `use_responses_api=False` ensures standard chat completions format, which is required for `create_react_agent` tool calling to work correctly
- `AZURE_OPENAI_API_VERSION` is no longer needed

> **Also drop `AgentServiceFactory`.** The new `AzureAIOpenAIApiChatModel` + `create_react_agent` from LangGraph handles agent orchestration directly without going through the Foundry Agents API, which eliminates all the `agents/write` permission issues entirely.

---

## Issue 8 — SQLite path not writable

### Symptom
`FileNotFoundError` or `OperationalError` when the app tries to create the SQLite database.

### Root Cause
The default path was `.data/finance_agent.db` (relative). On App Service, the working directory is a read-only extracted temp path (e.g. `/tmp/8de8da.../`). Relative paths resolve inside it but the parent `.data/` directory does not exist and the filesystem may be read-only outside `/tmp`.

### Resolution
Use `/tmp` as the database directory, which is always writable:

```python
# app/config.py
sqlite_db_path: str = "/tmp/finance_agent.db"
```

> **Note:** `/tmp` is ephemeral — data is lost on every restart or redeployment. For persistent storage migrate to Azure SQL, Azure Cosmos DB, or Azure Database for PostgreSQL.

---

## Quick-Reference Checklist

Before every deployment, verify:

- [ ] `startup.sh` exists at the repo root with `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- [ ] Startup command is registered: `az webapp config set --startup-file "startup.sh"`
- [ ] All secrets are in App Service Application Settings, not in any committed file
- [ ] System-assigned managed identity is enabled and has the **`Cognitive Services User`** role at the **account** scope (not project scope, not `Azure AI Developer`)
- [ ] `AZURE_OPENAI_ENDPOINT` does **not** have a trailing `/openai/v1` path — or better, use `AzureAIOpenAIApiChatModel` with `project_endpoint` so the setting is not needed at all
- [ ] LLM class is `AzureAIOpenAIApiChatModel` (not `AzureChatOpenAI`) if your resource kind is `AIServices`
- [ ] No module-level code in `agent.py` makes network calls or validates credentials
- [ ] SQLite path uses `/tmp/`

---

## Useful Diagnostic Commands

```bash
# Stream live logs
az webapp log tail --name fin-bot-api --resource-group $RG

# Download and inspect the latest docker log
az webapp log download --name fin-bot-api --resource-group $RG --log-file /tmp/app_logs.zip
unzip -p /tmp/app_logs.zip "LogFiles/*default_docker*" | tail -60

# Check current app settings keys (values not shown)
az webapp config appsettings list --name fin-bot-api --resource-group $RG --query "[].name"

# Inspect a specific setting value
az webapp config appsettings list --name fin-bot-api --resource-group $RG \
  --query "[?name=='AZURE_OPENAI_ENDPOINT'].value" -o tsv

# Check startup command
az webapp config show --name fin-bot-api --resource-group $RG --query appCommandLine

# Check managed identity
az webapp identity show --name fin-bot-api --resource-group $RG

# List ALL role assignments for the managed identity (including sub-scopes)
PRINCIPAL_ID=$(az webapp identity show --name fin-bot-api --resource-group $RG --query principalId -o tsv)
az role assignment list --assignee $PRINCIPAL_ID --all \
  --query "[].{role:roleDefinitionName, scope:scope}" -o table

# Check what data actions a role actually grants
az role definition list --name "Azure AI Developer" \
  --query "[0].permissions[0].dataActions" -o json

# Check if your AI resource is classic OpenAI or new AIServices kind
az cognitiveservices account show \
  --name <resource> --resource-group <rg> --query kind -o tsv

# List deployments and their capabilities
az cognitiveservices account deployment list \
  --name <resource> --resource-group <rg> \
  --query "[].{name:name, model:properties.model.name, capabilities:properties.capabilities}" -o json

# Test health endpoint
curl https://fin-bot-api.azurewebsites.net/health

# Test /brief endpoint
curl -X POST https://fin-bot-api.azurewebsites.net/brief \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL", "thread_id": "test-1"}'
```
