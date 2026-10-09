import hashlib
import json
import logging
import secrets
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from .models import Project, Message, Task, AgentRun, Approval, Document, Chunk
from .ai import respond, FIELDS
from .providers import AIError, request as ollama_request
from .retrieval import index_document

def permitted(user):
    return Project.objects.all() if user.is_staff else Project.objects.filter(owner=user)

def snapshot(p):
    return {'requirements': p.requirements, 'tasks': p.proposed_tasks}

def digest(p):
    return hashlib.sha256((p.approval_nonce + json.dumps(snapshot(p), sort_keys=True)).encode()).hexdigest()

def serialize(p):
    return {'id': p.id, 'name': p.name, 'status': p.status, 'owner': p.owner.username, 'requirements': p.requirements, 'provenance': p.provenance, 'proposed_tasks': p.proposed_tasks, 'approval_token': p.approval_token, 'version': p.version, 'messages': list(p.messages.order_by('id').values('role', 'content', 'sources')), 'tasks': list(p.tasks.values('id', 'title')), 'runs': list(p.runs.order_by('-id').values('id', 'status', 'model', 'trace', 'elapsed_ms', 'error')[:5])}

def body(request):
    try:
        data = json.loads(request.body or '{}')
        return data if isinstance(data, dict) else {}
    except (ValueError, UnicodeDecodeError): return {}

@login_required
def home(request):
    return render(request, 'index.html', {'mode': settings.AI_MODE, 'model': settings.OLLAMA_MODEL, 'fields': FIELDS})

@login_required
@require_http_methods(['GET', 'POST'])
def projects(request):
    if request.method == 'POST':
        name = body(request).get('name', '')
        if not isinstance(name, str) or not name.strip(): return JsonResponse({'error': 'Enter a project name.'}, status=400)
        p = Project.objects.create(owner=request.user, name=name.strip()[:150])
        Message.objects.create(project=p, role='assistant', content='Tell me about your website and the requirements you already know. I can search agency documents and prepare a task proposal for your manager.')
        return JsonResponse(serialize(p), status=201)
    return JsonResponse({'projects': [serialize(p) for p in permitted(request.user).order_by('-created_at')]})

@login_required
@require_http_methods(['GET'])
def project(request, pk): return JsonResponse(serialize(get_object_or_404(permitted(request.user), pk=pk)))

@login_required
@require_POST
def chat(request, pk):
    p = get_object_or_404(permitted(request.user), pk=pk)
    text = body(request).get('message', '')
    if not isinstance(text, str) or not text.strip() or len(text) > 8000: return JsonResponse({'error': 'Enter a message of 1–8,000 characters.'}, status=400)
    if p.status != 'discovery': return JsonResponse({'error': 'This handoff is locked for review or already approved.'}, status=409)
    try:
        result = respond(p, text, list(p.messages.order_by('id').values('role', 'content')))
    except Exception as exc:
        logging.getLogger(__name__).exception('Agent turn failed')
        explanation = str(exc) if isinstance(exc, AIError) else 'Unexpected AI response. No project changes were saved.'
        AgentRun.objects.create(project=p, actor=request.user, model=settings.OLLAMA_MODEL, status='failed', error=explanation)
        return JsonResponse({'error': explanation}, status=502)
    with transaction.atomic():
        updated = Project.objects.filter(pk=p.pk, version=p.version, status='discovery').update(requirements=result['requirements'], provenance=result['provenance'], proposed_tasks=result['plan'], approval_token='', version=F('version')+1)
        if not updated: return JsonResponse({'error': 'Project changed while the model was running. Refresh and retry; this turn was not saved.'}, status=409)
        Message.objects.create(project=p, role='user', content=text)
        Message.objects.create(project=p, role='assistant', content=result['reply'], sources=result['sources'])
        AgentRun.objects.create(project=p, actor=request.user, model=settings.OLLAMA_MODEL, trace=result['trace'], status='completed', elapsed_ms=result['elapsed_ms'])
    p.refresh_from_db()
    return JsonResponse(serialize(p))

@login_required
@require_POST
def review(request, pk):
    with transaction.atomic():
        p = get_object_or_404(permitted(request.user), pk=pk)
        if p.status != 'discovery': return JsonResponse({'error': 'Only discovery projects can be submitted.'}, status=409)
        if body(request).get('version') != p.version: return JsonResponse({'error': 'Brief changed. Refresh before submitting.'}, status=409)
        missing = [label for key, label in FIELDS.items() if not p.requirements.get(key)]
        if missing: return JsonResponse({'error': 'Complete: ' + ', '.join(missing)}, status=400)
        if not p.proposed_tasks: return JsonResponse({'error': 'Ask the assistant to propose project tasks first.'}, status=400)
        p.approval_nonce = secrets.token_hex(16)
        if not Project.objects.filter(pk=p.pk, version=p.version, status='discovery').update(status='review', approval_nonce=p.approval_nonce, approval_token=digest(p), version=F('version')+1): return JsonResponse({'error': 'Brief changed. Refresh.'}, status=409)
    p.refresh_from_db()
    return JsonResponse(serialize(p))

@login_required
@require_POST
def approve(request, pk):
    if not request.user.is_staff: return JsonResponse({'error': 'Agency manager access required.'}, status=403)
    data = body(request)
    if data.get('action') not in ['approve', 'revise']: return JsonResponse({'error': 'Choose approve or revise explicitly.'}, status=400)
    with transaction.atomic():
        p = get_object_or_404(Project, pk=pk)
        if not p.approval_token or data.get('approval_token') != p.approval_token or p.approval_token != digest(p): return JsonResponse({'error': 'Approval is missing or stale. Refresh and review the current proposal.'}, status=409)
        if p.status == 'approved' and data['action'] == 'approve': return JsonResponse(serialize(p))
        if p.status != 'review': return JsonResponse({'error': 'Submit for review first.'}, status=409)
        target = 'approved' if data['action'] == 'approve' else 'discovery'
        if not Project.objects.filter(pk=p.pk, version=p.version, status='review').update(status=target, version=F('version')+1): return JsonResponse({'error': 'Another reviewer changed this proposal.'}, status=409)
        Approval.objects.create(project=p, actor=request.user, decision=data['action'], token=p.approval_token, snapshot=snapshot(p))
        if target == 'approved':
            for title in p.proposed_tasks: Task.objects.get_or_create(project=p, title=title)
        else:
            Project.objects.filter(pk=p.pk).update(proposed_tasks=[], approval_token='')
            Message.objects.create(project=p, role='assistant', content='The manager requested revisions. Update your brief and ask for a new task proposal.')
    p.refresh_from_db()
    return JsonResponse(serialize(p))

@login_required
@require_http_methods(['GET', 'POST'])
def documents(request):
    if request.method == 'GET': return JsonResponse({'documents': list(Document.objects.values('id', 'title', 'updated_at')), 'chunks': Chunk.objects.count()})
    if not request.user.is_staff: return JsonResponse({'error': 'Only managers can edit shared agency knowledge.'}, status=403)
    data = body(request)
    try: doc = index_document(data.get('title'), data.get('content'))
    except ValueError as exc: return JsonResponse({'error': str(exc)}, status=400)
    except AIError as exc: return JsonResponse({'error': str(exc)}, status=502)
    return JsonResponse({'id': doc.pk, 'title': doc.title, 'chunks': doc.chunks.count()}, status=201)

@login_required
@require_http_methods(['GET'])
def ai_status(request):
    try:
        models = [m['name'] for m in ollama_request('/api/tags').get('models', [])]
        installed = lambda name: name in models or name + ':latest' in models
        ready = installed(settings.OLLAMA_MODEL) and installed(settings.OLLAMA_EMBED_MODEL) and Chunk.objects.filter(embedding_model=settings.OLLAMA_EMBED_MODEL).exists()
        return JsonResponse({'ready': ready, 'model': settings.OLLAMA_MODEL, 'embedding_model': settings.OLLAMA_EMBED_MODEL, 'indexed_chunks': Chunk.objects.count()})
    except AIError as exc: return JsonResponse({'ready': False, 'error': str(exc)}, status=503)
