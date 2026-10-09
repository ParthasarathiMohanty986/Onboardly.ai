from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from onboarding.models import Project, Message
class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for name, staff in [('client', False), ('manager', True)]:
            user, created = get_user_model().objects.get_or_create(username=name, defaults={'is_staff': staff})
            if created:
                user.set_password('OnboardDemo2026!'); user.save()
            if name == 'client':
                p, made = Project.objects.get_or_create(owner=user, name='Northline · Clothing storefront', defaults={'requirements': {'project_type': 'Ecommerce website', 'product_count': '50'}})
                if made:
                    Message.objects.create(project=p, role='user', content='We are Northline, a clothing brand. We need an ecommerce website with 50 products.')
                    Message.objects.create(project=p, role='assistant', content='I have added your website type and product count to the draft. Let’s fill in the remaining details. What budget range and currency do you have in mind?')
        self.stdout.write('Demo ready: client / manager. New user password: OnboardDemo2026!')
