import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from .models import Project, Message, Task
from .ai import respond, FIELDS

def permitted(user):
    return Project.objects.all() if user.is_staff else Project.objects.filter(owner=user)

def serialize(p):
    return {'id': p.id, 'name': p.name, 'status': p.status, 'owner': p.owner.username, 'requirements': p.requirements, 'messages': list(p.messages.values('role', 'content', 'sources')), 'tasks': list(p.tasks.values('id', 'title'))}

def body(request):
    try:
        data = json.loads(request.body or '{}')
        return data if isinstance(data, dict) else {}
    except (ValueError, UnicodeDecodeError): return {}

@login_required
def home(request):
    return render(request, 'index.html', {'mode': settings.AI_MODE, 'fields': FIELDS})

@login_required
@require_http_methods(['GET', 'POST'])
def projects(request):
    if request.method == 'POST':
        name = body(request).get('name', '')
        if not isinstance(name, str) or not name.strip(): return JsonResponse({'error': 'Enter a project name.'}, status=400)
        p = Project.objects.create(owner=request.user, name=name.strip()[:150])
        Message.objects.create(project=p, role='assistant', content='Welcome! Tell me about your website, its goals, and anything you already know about the scope.')
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
    try: reply, updates, sources = respond(text, p.requirements, list(p.messages.values('role', 'content')))
    except Exception:
        return JsonResponse({'error': 'AI service unavailable or returned invalid data. Check Ollama is running and OLLAMA_MODEL is installed. Your message was not saved; try again.'}, status=502)
    with transaction.atomic():
        p = Project.objects.select_for_update().get(pk=p.pk)
        if p.status != 'discovery': return JsonResponse({'error': 'Project state changed. Refresh and try again.'}, status=409)
        p.requirements = {**p.requirements, **updates}
        p.save(update_fields=['requirements'])
        Message.objects.create(project=p, role='user', content=text)
        Message.objects.create(project=p, role='assistant', content=reply, sources=sources)
    return JsonResponse(serialize(p))

@login_required
@require_POST
def review(request, pk):
    with transaction.atomic():
        p = get_object_or_404(permitted(request.user).select_for_update(), pk=pk)
        if p.status != 'discovery': return JsonResponse({'error': 'Only discovery projects can be submitted.'}, status=409)
        missing = [label for key, label in FIELDS.items() if not p.requirements.get(key)]
        if missing: return JsonResponse({'error': 'Complete these fields first: ' + ', '.join(missing)}, status=400)
        p.status = 'review'; p.save(update_fields=['status'])
    return JsonResponse(serialize(p))

@login_required
@require_POST
def approve(request, pk):
    if not request.user.is_staff: return JsonResponse({'error': 'Agency manager access required.'}, status=403)
    with transaction.atomic():
        p = get_object_or_404(Project.objects.select_for_update(), pk=pk)
        if p.status == 'approved': return JsonResponse(serialize(p))
        if p.status != 'review': return JsonResponse({'error': 'Submit the handoff for review first.'}, status=409)
        if body(request).get('action') == 'revise':
            p.status = 'discovery'; p.save(update_fields=['status'])
            Message.objects.create(project=p, role='assistant', content='Your agency manager reopened this brief for revisions. Update any requirement using field_name: value.')
        else:
            for title in ['Confirm scope, budget and delivery schedule', 'Collect and review brand assets', 'Design storefront and approve layouts', 'Configure catalogue and payment integration', 'Test checkout and prepare launch']:
                Task.objects.get_or_create(project=p, title=title)
            p.status = 'approved'; p.save(update_fields=['status'])
    return JsonResponse(serialize(p))
