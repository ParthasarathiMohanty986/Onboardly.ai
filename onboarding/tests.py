from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from .models import Project, Task, Approval, AgentRun, Document, Chunk
from .ai import FIELDS, AgentSession, respond
from .providers import AIError
from .retrieval import index_document, retrieve

def call(name, args):
    return {'role':'assistant','content':'','tool_calls':[{'function':{'name':name,'arguments':args}}]}

class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user('client')
        cls.other=get_user_model().objects.create_user('other')
        cls.manager=get_user_model().objects.create_user('manager',is_staff=True)

    def setUp(self):
        self.p=Project.objects.create(owner=self.user,name='Test')
        self.client.force_login(self.user)

    def post(self,path,data=None):
        return self.client.post(f'/api/projects/{self.p.pk}/{path}/',data=data or {},content_type='application/json')

    def ready(self):
        self.p.requirements={k:'Provided' for k in FIELDS}
        self.p.proposed_tasks=['Design clothing catalogue','Integrate Razorpay checkout']
        self.p.save()
        response=self.post('review',{'version':self.p.version})
        self.assertEqual(response.status_code,200)
        self.p.refresh_from_db()
        return self.p.approval_token

    def test_isolation(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/api/projects/{self.p.pk}/').status_code,404)
        self.assertEqual(self.post('chat',{'message':'hello'}).status_code,404)

    def test_no_approval_from_client(self):
        self.assertEqual(self.post('approve',{'action':'approve'}).status_code,403)

    def test_approval_exact_plan_and_idempotency(self):
        token=self.ready();self.client.force_login(self.manager)
        payload={'action':'approve','approval_token':token}
        self.assertEqual(self.post('approve',payload).status_code,200)
        self.assertEqual(self.post('approve',payload).status_code,200)
        self.assertEqual(list(Task.objects.values_list('title',flat=True)),self.p.proposed_tasks)
        self.assertEqual(Approval.objects.count(),1)

    def test_stale_or_missing_approval_rejected(self):
        self.ready();self.client.force_login(self.manager)
        self.assertEqual(self.post('approve',{'action':'approve'}).status_code,409)
        token=self.p.approval_token
        self.p.proposed_tasks=['Changed proposal'];self.p.save()
        self.assertEqual(self.post('approve',{'action':'approve','approval_token':token}).status_code,409)
        self.assertEqual(Task.objects.count(),0)

    def test_incomplete_and_planless_submission(self):
        self.assertEqual(self.post('review',{'version':0}).status_code,400)
        self.p.requirements={k:'Provided' for k in FIELDS};self.p.save()
        self.assertEqual(self.post('review',{'version':0}).status_code,400)

    def test_revision_invalidates_plan(self):
        token=self.ready();self.client.force_login(self.manager)
        self.assertEqual(self.post('approve',{'action':'revise','approval_token':token}).status_code,200)
        self.p.refresh_from_db();self.assertEqual(self.p.status,'discovery');self.assertEqual(self.p.proposed_tasks,[])
        self.assertEqual(self.post('approve',{'action':'approve','approval_token':token}).status_code,409)

    @patch('onboarding.ai.chat_completion')
    def test_model_selected_tools_persist(self, model):
        model.side_effect=[call('update_requirement',{'field':'budget','value':'INR 80000','evidence':'My budget is INR 80000'}),{'role':'assistant','content':'Budget saved as a draft. What is your launch date?'}]
        self.assertEqual(self.post('chat',{'message':'My budget is INR 80000'}).status_code,200)
        self.p.refresh_from_db();self.assertEqual(self.p.requirements,{'budget':'INR 80000'})
        self.assertEqual(AgentRun.objects.get().trace[0]['tool'],'update_requirement')
        self.assertEqual(model.call_args[0][0][-1]['role'],'tool')

    @patch('onboarding.ai.chat_completion')
    def test_provider_failure_rolls_back_staged_changes(self, model):
        model.side_effect=[call('update_requirement',{'field':'budget','value':'100','evidence':'100'}),AIError('Offline')]
        self.assertEqual(self.post('chat',{'message':'100'}).status_code,502)
        self.p.refresh_from_db();self.assertEqual(self.p.requirements,{})
        self.assertEqual(self.p.messages.count(),0)
        self.assertEqual(AgentRun.objects.get().status,'failed')

    def test_tool_permissions_and_evidence(self):
        session=AgentSession(self.p,'Hello')
        with self.assertRaises(ValueError): session.execute('approve',{})
        with self.assertRaises(ValueError): session.execute('get_project',{'project_id':42})
        with self.assertRaises(ValueError): session.execute('update_requirement',{'field':'budget','value':'100','evidence':'Invented'})
        with self.assertRaises(ValueError): session.execute('propose_tasks',{'tasks':['Task one','Task two']})

    def test_reapproval_nonce_prevents_replay(self):
        first=self.ready();self.client.force_login(self.manager)
        self.post('approve',{'action':'revise','approval_token':first})
        self.p.refresh_from_db()
        self.p.proposed_tasks=['Design clothing catalogue','Integrate Razorpay checkout'];self.p.save()
        self.post('review',{'version':self.p.version})
        self.p.refresh_from_db()
        self.assertNotEqual(first,self.p.approval_token)
        self.assertEqual(self.post('approve',{'action':'approve','approval_token':first}).status_code,409)

    @patch('onboarding.ai.chat_completion')
    def test_failed_tool_cannot_be_reported_as_success(self,model):
        model.side_effect=[call('search_documents',{'query':{'value':'photos'}}),{'role':'assistant','content':'Done'},call('get_project',{}),{'role':'assistant','content':'I could not retrieve the policy.'}]
        result=respond(self.p,'photos?',[])
        self.assertEqual(model.call_count,4)
        self.assertIn('error',result['trace'][0]['result'])

    @override_settings(AI_MAX_ROUNDS=2)
    @patch('onboarding.ai.chat_completion',return_value=call('get_project',{}))
    def test_loop_is_bounded(self,model):
        with self.assertRaises(AIError): respond(self.p,'Hello',[])
        self.assertEqual(model.call_count,2)

    def test_locked_handoff(self):
        self.ready()
        self.assertEqual(self.post('chat',{'message':'Change budget'}).status_code,409)

    def test_invalid_input_and_document_permissions(self):
        self.assertEqual(self.post('chat',{'message':42}).status_code,400)
        self.assertEqual(self.client.post('/api/documents/',{'title':'policy','content':'test'},content_type='application/json').status_code,403)

    @patch('onboarding.retrieval.embed')
    def test_dense_retrieval_and_atomic_reindex(self,embed):
        embed.return_value=[[1.0,0.0]]
        doc=index_document('Support','We repair bugs for thirty days after launch.')
        other=Document.objects.create(title='Other',content='Other',fingerprint='test')
        Chunk.objects.create(document=other,position=0,text='Unrelated',embedding=[0.0,1.0],embedding_model='embeddinggemma')
        rows=retrieve('Will you fix defects after delivery?')
        self.assertEqual(rows[0]['document_id'],doc.id)
        embed.side_effect=AIError('Offline')
        with self.assertRaises(AIError): index_document('Support','Updated document content that cannot be embedded.')
        doc.refresh_from_db();self.assertIn('thirty',doc.content);self.assertEqual(doc.chunks.count(),1)

    @patch('onboarding.views.respond')
    def test_concurrent_update_does_not_overwrite(self,model):
        def stale(*args):
            Project.objects.filter(pk=self.p.pk).update(version=1,requirements={'budget':'Newer'})
            return {'requirements':{},'provenance':{},'plan':[],'reply':'Old','sources':[],'trace':[],'elapsed_ms':1}
        model.side_effect=stale
        self.assertEqual(self.post('chat',{'message':'hello'}).status_code,409)
        self.p.refresh_from_db();self.assertEqual(self.p.requirements['budget'],'Newer')
