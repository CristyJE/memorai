# MemorAI 🧠🌸

> *"Your loved one's story deserves to outlive them."*

MemorAI is an AI-powered life story digitization platform built for Filipino families — especially Overseas Filipino Workers (OFWs) — to capture and preserve the voices, memories, and wisdom of their aging loved ones through guided, conversational AI interviews.

Built entirely on **Microsoft Azure**.

---

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Azure services used](#azure-services-used)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [Running locally](#running-locally)
- [Deploying to Azure](#deploying-to-azure)
- [API reference](#api-reference)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

MemorAI conducts gentle, guided weekly voice interviews with seniors in Filipino, Ilocano, or Bisaya. The AI remembers every detail across sessions and weaves them into a polished memoir — delivered as a private family website, a printed hardcover book, or a narrated video.

**Core flow:**
1. Family gifts a subscription and sets up a tablet or smart speaker for their loved one
2. MemorAI's interview agent conducts weekly 15–20 minute voice conversations
3. Stories are transcribed, stored, and semantically indexed
4. Uploaded photos are enriched and linked to story chapters
5. Azure OpenAI generates a polished, chapter-structured memoir
6. The family receives the memoir via a private portal, PDF book, or narrated video

---

## Architecture

```
Senior device (tablet / smart speaker)
        │  voice in/out
        ▼
┌─────────────────────────────────────────────────────┐
│                 CONVERSATION LAYER                  │
│  Azure AI Speech   ·   Azure OpenAI (GPT-4o)        │
│  Microsoft Agent Framework (session memory)         │
└──────────────────────┬──────────────────────────────┘
                       │ events
                       ▼
┌─────────────────────────────────────────────────────┐
│               ORCHESTRATION LAYER                   │
│              Azure Functions (Python)               │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────┐  ┌──────────────┐  ┌───────────────┐
│ Cosmos DB│  │  AI Search   │  │  AI Vision    │
│ stories  │  │  semantic    │  │  photos       │
└──────────┘  │  index       │  └───────────────┘
              └──────────────┘
       │ memoir output
       ▼
┌─────────────────────────────────────────────────────┐
│                  DELIVERY LAYER                     │
│  Azure App Service  ·  AI Translator                │
│  Family portal  ·  PDF  ·  Video memoir             │
└─────────────────────────────────────────────────────┘
              ↑ underpinned by
      Microsoft Foundry (model orchestration)
```

---

## Azure services used

| Service | Role |
|---|---|
| **Microsoft Foundry** | Model orchestration and deployment foundation |
| **Azure OpenAI (GPT-4o)** | Interview intelligence and memoir writing |
| **Azure AI Speech** | Voice input/output, tuned for elderly cadence |
| **Azure AI Search** | Semantic indexing of story fragments |
| **Azure Cosmos DB** | NoSQL story storage (chapter-tagged fragments) |
| **Azure Functions** | Event-driven pipeline orchestration |
| **Azure App Service** | Family memoir portal (FastAPI) |
| **Microsoft Agent Framework** | Cross-session memory and chapter management |
| **Azure AI Vision** | Photo enrichment and era tagging |
| **Azure AI Translator** | Filipino, Ilocano, and Bisaya output |

---

## Project structure

```
memorai/
├── README.md
├── .env.example                  # Environment variable template
├── .gitignore
├── requirements.txt              # Python dependencies
│
├── agents/                       # Microsoft Agent Framework
│   ├── __init__.py
│   ├── interview_agent.py        # Main interview orchestrator
│   └── memoir_agent.py           # Memoir compilation agent
│
├── services/                     # Azure service wrappers
│   ├── __init__.py
│   ├── speech.py                 # Azure AI Speech (STT + TTS)
│   ├── openai_client.py          # Azure OpenAI client
│   ├── cosmos_db.py              # Cosmos DB story storage
│   ├── ai_search.py              # Azure AI Search indexing
│   ├── ai_vision.py              # Photo enrichment
│   └── translator.py             # Azure AI Translator
│
├── api/                          # Azure Functions
│   ├── interview_session/
│   │   ├── __init__.py           # HTTP trigger: start/continue interview
│   │   └── function.json
│   ├── memoir_generator/
│   │   ├── __init__.py           # Timer/queue trigger: compile memoir
│   │   └── function.json
│   └── photo_enrichment/
│       ├── __init__.py           # Blob trigger: process uploaded photo
│       └── function.json
│
├── app/                          # Azure App Service — family portal
│   ├── main.py                   # FastAPI entrypoint
│   ├── routers/
│   │   ├── memoir.py             # Memoir retrieval endpoints
│   │   └── profile.py            # Senior profile management
│   └── templates/
│       └── memoir.html           # Memoir viewer template
│
├── infra/                        # Infrastructure as code
│   ├── main.bicep                # Azure Bicep main template
│   └── parameters.json           # Deployment parameters
│
├── tests/
│   ├── test_interview_agent.py
│   ├── test_memoir_agent.py
│   └── test_services.py
│
└── docs/
    └── architecture.png
```

---

## Getting started

### Prerequisites

- Python 3.11+
- Azure CLI (`az`) authenticated to your subscription
- An Azure resource group with the services listed above provisioned
- [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local) v4+

### 1. Clone the repo

```bash
git clone https://github.com/your-org/memorai.git
cd memorai
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your Azure resource credentials
```

### 4. Run locally

```bash
# Start the Azure Functions runtime
cd api && func start

# In a separate terminal, start the App Service portal
cd app && uvicorn main:app --reload
```

---

## Environment variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Your Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | GPT-4o deployment name |
| `AZURE_SPEECH_KEY` | Azure AI Speech subscription key |
| `AZURE_SPEECH_REGION` | Azure region (e.g. `southeastasia`) |
| `COSMOS_ENDPOINT` | Cosmos DB account endpoint |
| `COSMOS_KEY` | Cosmos DB account key |
| `COSMOS_DB_NAME` | Database name (e.g. `memorai`) |
| `SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `SEARCH_API_KEY` | Azure AI Search admin key |
| `VISION_ENDPOINT` | Azure AI Vision endpoint |
| `VISION_KEY` | Azure AI Vision key |
| `TRANSLATOR_KEY` | Azure AI Translator key |
| `TRANSLATOR_REGION` | Azure region for Translator |

---

## Deploying to Azure

```bash
# Deploy infrastructure
az deployment group create \
  --resource-group memorai-rg \
  --template-file infra/main.bicep \
  --parameters @infra/parameters.json

# Deploy Azure Functions
cd api && func azure functionapp publish memorai-functions

# Deploy App Service
cd app && az webapp up --name memorai-portal --runtime PYTHON:3.11
```

---

## API reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/interview/start` | POST | Begin a new interview session |
| `/api/interview/respond` | POST | Send senior's response, receive next question |
| `/api/memoir/{senior_id}` | GET | Retrieve compiled memoir |
| `/api/memoir/{senior_id}/generate` | POST | Trigger memoir compilation |
| `/api/profile/{senior_id}` | GET/POST | Manage senior profile |
| `/api/photos/upload` | POST | Upload and enrich a photo |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'add: your feature description'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a pull request

Please follow the existing code structure and add tests for new features.

---

## License

MIT License. See `LICENSE` for details.

---

*Built with 💙 for Filipino families. Powered by Microsoft Azure.*
