# Onboardly — Client onboarding assistant

Working Django prototype: client/manager login, persistent projects, chat, requirements checklist, sample policy retrieval, manager review, revisions, and approval-based task creation.

## Run locally (PowerShell)

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

Visit http://127.0.0.1:8000. Local users: `client` and `manager`, both password `OnboardDemo2026!`. Development-only credentials and configuration.

## Try it

Sign in as client and send this to the Northline project:

```text
budget: INR 80,000
launch_date: 15 December 2026
payment_methods: Razorpay
brand_assets: Logo and photos ready
```

Ask `Does the package include photography?`, review the checklist, and submit. Sign out and log in as manager to approve or request revisions. Approval creates five starter tasks without duplicates.

## Live AI

Install Ollama separately and pull a model supporting structured outputs. Set the exact installed model name:

```powershell
$env:AI_MODE = 'ollama'
$env:OLLAMA_MODEL = 'YOUR_INSTALLED_MODEL_NAME'
python manage.py runserver 127.0.0.1:8000
```

OLLAMA_URL defaults to http://localhost:11434. No model is automatically installed. The adapter sends sample policy context and recent conversation history to /api/chat and validates basic response shape. Live integration is unverified without a running model. Failures are visible rather than silently replaced with demo responses.

## Scope and next stages

This initial vertical slice uses SQLite, deterministic demo extraction, lexical retrieval, and a fixed approval workflow. Sample agency policies are fictional fixtures in onboarding/ai.py. Staff can access all projects in this single-agency prototype. Tasks are fixed starter templates.

Not yet implemented: LangChain, LangGraph, Pydantic, embeddings, pgvector, PDF uploads, model-driven tool calling, dynamic task generation, or production deployment. Next stages are evaluated vector retrieval, schemas/provenance, scoped Django tools and persisted agent orchestration. Do not treat this demo as the complete proposed AI stack.

Before deployment: use supported patched dependencies, secret management, DEBUG off, HTTPS, configured hosts, a production database, rate limits, concurrency hardening and remove demo accounts. AI output still needs factual review even when valid JSON.

Run tests: `python manage.py test`.
