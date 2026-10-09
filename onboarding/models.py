from django.db import models
from django.conf import settings

class Project(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, default='discovery')
    requirements = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    project = models.ForeignKey(Project, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=20)
    content = models.TextField()
    sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'title'], name='unique_project_task')]
