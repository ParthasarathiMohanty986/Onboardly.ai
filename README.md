# AI Client Onboarding · Onboardly

A Django application using **real local LLM inference, dense document embeddings, semantic retrieval and model-selected tool calls**. Clients develop a brief through chat; a manager approves the exact task proposal before Django creates tasks.

## Stack

- Python / Django: authentication, scoped APIs, persistence and approval enforcement.
- Ollama + Qwen3 4B: language generation and native function/tool calling.
- Ollama + EmbeddingGemma: dense document/query embeddings.
- SQLite: application records and persisted embedding arrays. Python performs exact cosine similarity search over a small corpus. This is genuine vector retrieval, but not an indexed vector database.
- HTML, CSS and JavaScript: chat, checklist, proposals, source passages, agent trace and manager document editor.

There is no rule-based chat fallback. Provider failure is visible and staged changes are discarded. LangChain, LangGraph, Pydantic and pgvector are **not** dependencies: orchestration and validation are explicit Python so the execution path is easy to learn. A PostgreSQL/pgvector migration remains a future scaling step.

## Local setup (PowerShell)

Install Python and Ollama, then run these commands in this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen3:4b
ollama pull embeddinggemma
python manage.py migrate
python manage.py seed_demo
python manage.py index_documents
python manage.py runserver 127.0.0.1:8000
```

The recommended model downloads total about 3.1 GB. Ollama must be running. Open http://127.0.0.1:8000. Sample accounts: `client` and `manager`; both passwords are `OnboardDemo2026!`. Only use these credentials in local development.

Defaults work without API keys. Optional configuration:

```powershell
$env:OLLAMA_URL = 'http://localhost:11434'
$env:OLLAMA_MODEL = 'qwen3:4b'
$env:OLLAMA_EMBED_MODEL = 'embeddinggemma'
```

Model changes may alter tool reliability. Reindex documents whenever the embedding model or its weights change. Inference latency depends on your hardware; a multi-tool turn may take minutes on a CPU.

## Try the full workflow

1. Sign in as client; create a project or choose Northline.
2. Ask: `Does the package include product photography?` The model chooses `search_documents`, which embeds the query and retrieves policy passages. Expand **Agent activity & source passages** to inspect the real function arguments, results and source text.
3. Supply facts: `My budget is INR 80000. The target launch is 15 December 2026. We want Razorpay payments. Our logo and product photos are ready.` The model chooses requirement-update tools. Review the extracted facts; hover over a checklist field to see its evidence quote. Correct any error in chat.
4. Once all six fields are populated, click **Draft task proposal**. The model proposes project-specific titles. No Task records exist yet.
5. Review the visible proposal and click **Submit for review**. This freezes the snapshot.
6. Log in as manager. Approve the displayed proposal or request revisions. Only the approval endpoint creates those exact task records.

Existing conversations from the old prototype remain in the database. Their historical responses were rule-based; new turns use the live agent. Verification projects are explicitly named `Live AI verification`.

## Documents and retrieval

`knowledge/` contains four fictional agency policies. The indexing command loads `.md` and `.txt` files, splits them into overlapping character windows, generates embeddings and stores text, source metadata and vectors. Reindexing a title replaces its passages only after embedding succeeds.

Managers can also paste a title and policy text in **Manage agency knowledge**. These are shared agency documents visible to all authenticated clients in this single-agency prototype. Private client uploads, PDF extraction, OCR and multi-agency isolation are not implemented.

Retrieval filters by embedding model, ranks by cosine similarity, and supplies up to four passages. A similarity threshold is a heuristic, not a guarantee of relevance or factual correctness. Source text remains visible for human verification.

## Tools and approval boundaries

| Tool | Operation |
|---|---|
| `get_project` | Read the current scoped brief |
| `search_documents` | Search the shared agency knowledge base |
| `update_requirement` | Stage a draft value with an exact quote from the latest client message |
| `propose_tasks` | Stage a plan for review; never execute it |

No tool accepts a project/user ID or executes code/SQL. No model-callable approval function exists. A bounded loop sends tool results back to the LLM. If inference fails or the loop exceeds its limits, draft mutations are not committed.

Successful turns save messages, provenance and tool traces atomically. Optimistic version checks reject stale concurrent writes. Submission creates a snapshot-bound token with a fresh nonce. Manager approval requires this exact token, checks the current snapshot and records the actor and decision. Repeated approval is idempotent. Revisions invalidate the proposal and require fresh review.

These controls limit actions, but a small LLM can still select an irrelevant tool, misunderstand a fact or produce an unsupported answer. Evidence quotes are checked literally; semantic correctness still needs review. The app is a learning/portfolio prototype, not production-ready.

## Verification

```powershell
python manage.py test
python manage.py verify_live_ai
```

Unit tests use mocked model responses to test deterministic safety properties. The opt-in live command uses the real installed models and creates a labeled sample project: semantic paraphrase search, model-selected retrieval, requirement update, task proposal, blocked client approval, manager approval and duplicate prevention.

Useful files: `onboarding/ai.py` (agent loop/tools), `providers.py` (Ollama HTTP), `retrieval.py` (indexing/search), `views.py` (permissions/approval), and `tests.py`.

## Before production

Use a supported patched Django version, secret management, HTTPS, DEBUG off, rate limits, bounded background jobs, stronger model evaluations, and a production database. Remove demo users, review trace retention, add upload controls if supporting files, and implement tenancy before hosting multiple agencies. Local databases and credentials are excluded from Git.
