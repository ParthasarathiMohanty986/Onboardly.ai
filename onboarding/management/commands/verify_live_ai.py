"""Opt-in real inference smoke test. Leaves a clearly named demonstration project."""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.test import Client
from onboarding.models import Project, Task
from onboarding.retrieval import retrieve

class Command(BaseCommand):
    help='Run real model retrieval, tool calls, and approval roundtrip with sample data.'
    def handle(self,*args,**kwargs):
        client_user=get_user_model().objects.get(username='client')
        manager=get_user_model().objects.get(username='manager')
        client=Client();client.force_login(client_user)
        p=Project.objects.create(owner=client_user,name='Live AI verification · clothing store',requirements={'project_type':'Clothing ecommerce','product_count':'50','budget':'INR 80000','launch_date':'15 December 2026','payment_methods':'Razorpay','brand_assets':'Logo and photos ready'})
        rows=retrieve('Will you repair defects after the site goes live?')
        if not rows or 'support' not in rows[0]['title'].lower():raise CommandError('Semantic retrieval failed expected support match.')
        self.stdout.write('PASS real embeddings: paraphrased query retrieved Support')
        for prompt,expected in [('Does the standard package include product photography?','search_documents'),('My budget is now INR 90000. Update my budget.','update_requirement'),('Propose a task plan for this clothing ecommerce project using the requirements.','propose_tasks')]:
            self.stdout.write('Running real model: '+prompt)
            response=client.post(f'/api/projects/{p.pk}/chat/',{'message':prompt},content_type='application/json')
            if response.status_code!=200:raise CommandError(str(response.json()))
            result=response.json()
            tools=[t['tool'] for t in result['runs'][0]['trace']]
            self.stdout.write('Tools: '+str(tools)+'\nReply: '+result['messages'][-1]['content'])
            if expected not in tools:raise CommandError('Expected model-selected tool missing: '+expected)
            if not any(t['tool']==expected and not t['result'].get('error') for t in result['runs'][0]['trace']):raise CommandError('Model tool never executed successfully.')
            if expected=='search_documents' and not result['messages'][-1]['sources']:raise CommandError('No source passages retrieved.')
            if expected=='search_documents' and not any(phrase in result['messages'][-1]['content'].lower() for phrase in ['not included','does not include','separate quote','not include']):raise CommandError('Policy answer did not state the photography exclusion.')
            if expected=='update_requirement' and '90000' not in result['requirements'].get('budget',''):raise CommandError('Budget update was not persisted.')
            if expected=='propose_tasks' and not result['proposed_tasks']:raise CommandError('No task proposal persisted.')
        p.refresh_from_db()
        if Task.objects.filter(project=p).exists():raise CommandError('Tasks were created without approval!')
        response=client.post(f'/api/projects/{p.pk}/review/',{'version':p.version},content_type='application/json')
        if response.status_code!=200:raise CommandError(str(response.json()))
        data={'action':'approve','approval_token':response.json()['approval_token']}
        if client.post(f'/api/projects/{p.pk}/approve/',data,content_type='application/json').status_code!=403:raise CommandError('Client approval was not blocked.')
        client.force_login(manager)
        for _ in range(2):
            response=client.post(f'/api/projects/{p.pk}/approve/',data,content_type='application/json')
            if response.status_code!=200:raise CommandError(str(response.json()))
        p.refresh_from_db()
        if p.tasks.count()!=len(p.proposed_tasks):raise CommandError('Task counts do not match approved proposal.')
        self.stdout.write(self.style.SUCCESS(f'PASS live LLM, semantic retrieval, model tools, manager approval and idempotency. Project #{p.pk}'))
