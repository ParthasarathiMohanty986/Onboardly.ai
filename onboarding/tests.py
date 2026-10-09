from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Project, Task
from .ai import FIELDS, respond
class WorkflowTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('client',password='test')
        self.other=get_user_model().objects.create_user('other',password='test')
        self.manager=get_user_model().objects.create_user('manager',password='test',is_staff=True)
        self.p=Project.objects.create(owner=self.user,name='Test')
        self.client.force_login(self.user)
    def post(self,path,data=None):return self.client.post(f'/api/projects/{self.p.pk}/{path}/',data=data or {},content_type='application/json')
    def test_isolation(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/api/projects/{self.p.pk}/').status_code,404)
        self.assertEqual(self.post('chat',{'message':'hello'}).status_code,404)
    def test_approval_permissions_and_idempotency(self):
        self.assertEqual(self.post('approve').status_code,403)
        self.assertEqual(self.post('review').status_code,400)
        self.p.requirements={k:'Provided' for k in FIELDS};self.p.save()
        self.assertEqual(self.post('review').status_code,200)
        self.assertEqual(self.post('chat',{'message':'budget: 10'}).status_code,409)
        self.client.force_login(self.manager)
        self.assertEqual(self.post('approve').status_code,200)
        self.assertEqual(self.post('approve').status_code,200)
        self.assertEqual(Task.objects.count(),5)
    def test_chat_persists_and_unknown_stays_missing(self):
        self.assertEqual(self.post('chat',{'message':'I need an ecommerce website with 50 products.'}).status_code,200)
        self.p.refresh_from_db();self.assertEqual(self.p.requirements['product_count'],'50')
        self.assertNotIn('budget',self.p.requirements)
        self.assertEqual(self.p.messages.count(),2)
    def test_revision(self):
        self.p.status='review';self.p.save();self.client.force_login(self.manager)
        self.assertEqual(self.post('approve',{'action':'revise'}).status_code,200)
        self.p.refresh_from_db();self.assertEqual(self.p.status,'discovery');self.assertEqual(Task.objects.count(),0)
    def test_policy_sources(self):
        reply,updates,sources=respond('Does the package include photography?',{},[])
        self.assertTrue(sources);self.assertIn('not included',reply);self.assertFalse(updates)
    def test_invalid_input(self):
        self.assertEqual(self.post('chat',{'message':42}).status_code,400)
        self.assertEqual(self.post('chat',{'message':'a'*8001}).status_code,400)
