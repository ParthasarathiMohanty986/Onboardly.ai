from django.db import models
from django.conf import settings

class Project(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, default='discovery')
    requirements = models.JSONField(default=dict)
    provenance = models.JSONField(default=dict)
    proposed_tasks = models.JSONField(default=list)
    approval_token = models.CharField(max_length=64, blank=True)
    approval_nonce = models.CharField(max_length=32, blank=True)
    version = models.PositiveIntegerField(default=0)
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

class Document(models.Model):
    title = models.CharField(max_length=180, unique=True)
    content = models.TextField()
    fingerprint = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

class Chunk(models.Model):
    document = models.ForeignKey(Document, related_name='chunks', on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    text = models.TextField()
    embedding = models.JSONField()
    embedding_model = models.CharField(max_length=120)

class AgentRun(models.Model):
    project = models.ForeignKey(Project, related_name='runs', on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    model = models.CharField(max_length=120)
    trace = models.JSONField(default=list)
    status = models.CharField(max_length=20)
    error = models.TextField(blank=True)
    elapsed_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Approval(models.Model):
    project = models.ForeignKey(Project, related_name='approvals', on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20)
    snapshot = models.JSONField()
    token = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
