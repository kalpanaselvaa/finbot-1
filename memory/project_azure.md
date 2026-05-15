---
name: project-azure
description: Azure configuration and current status for cb-finbot
metadata: 
  node_type: memory
  type: project
  originSessionId: 799d0a03-80c9-4f43-a33f-b00d3d2bb93a
---

Azure subscription is currently disabled — all Azure paths fail open or are skipped.

**Why:** Subscription `f1d64acd-32c9-4753-9677-7377652e4006` ("Azure subscription 1") is disabled/read-only. Needs re-enabling via portal.azure.com (likely billing/trial expiry).

**How to apply:** Do not rely on Azure for any currently working functionality. When subscription is re-enabled, run `az provider register --namespace Microsoft.CognitiveServices` first.

## .env values (as of session)
- `AZURE_OPENAI_ENDPOINT` = `https://cb-ai-bootcamp-resource.openai.azure.com/openai/v1`
- `AZURE_OPENAI_DEPLOYMENT` = `gpt-oss-120b`
- `AZURE_AI_PROJECT_ENDPOINT` = `https://cb-ai-bootcamp-resource.services.ai.azure.com/api/projects/cb-ai-bootcamp`
- `AZURE_CONTENT_SAFETY_ENDPOINT` = `https://cb-ai-bootcamp-resource.cognitiveservices.azure.com/`
- `SERPAPI_API_KEY` = empty (key was invalid, cleared)

## What activates when Azure is re-enabled
1. `app/agent.py` — swap `ChatOllama` back to `AzureAIOpenAIApiChatModel` with `DefaultAzureCredential`
2. `app/guardrails.py` — `_azure_available` flag resets; Azure Content Safety takes priority over local llama3.2

## Azure agent details
- Agent ID: `fin-bot-agent:3`
- Resource: `/subscriptions/f1d64acd-.../resourceGroups/rg-kalpanaselvaa-8325/providers/Microsoft.CognitiveServices/accounts/cb-ai-bootcamp-resource`
- Location: eastus2
