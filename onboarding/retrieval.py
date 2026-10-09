"""Persistent dense vectors and exact cosine search for a small local corpus."""
import hashlib
import math
from django.conf import settings
from django.db import transaction
from .models import Document, Chunk
from .providers import embed, AIError

def index_document(title, content):
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 180: raise ValueError('Title must be 1–180 characters.')
    if not isinstance(content, str) or not 20 <= len(content.strip()) <= 100000: raise ValueError('Text must be 20–100,000 characters.')
    pieces = [content[i:i+1200] for i in range(0, len(content), 1000)]
    vectors = []
    for start in range(0, len(pieces), 16): vectors.extend(embed(pieces[start:start+16]))
    with transaction.atomic():
        doc, _ = Document.objects.get_or_create(title=title.strip())
        doc.content = content
        doc.fingerprint = hashlib.sha256(content.encode()).hexdigest()
        doc.save()
        doc.chunks.all().delete()
        Chunk.objects.bulk_create([Chunk(document=doc, position=i, text=text, embedding=vector, embedding_model=settings.OLLAMA_EMBED_MODEL) for i, (text, vector) in enumerate(zip(pieces, vectors))])
    return doc

def cosine(a, b):
    if len(a) != len(b): raise AIError('Embedding dimensions changed. Reindex documents.')
    return sum(x*y for x,y in zip(a,b)) / (math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(y*y for y in b)))

def retrieve(query):
    chunks = list(Chunk.objects.select_related('document').filter(embedding_model=settings.OLLAMA_EMBED_MODEL))
    if not chunks: raise AIError('No indexed documents for this model. Run python manage.py index_documents.')
    vector = embed([query])[0]
    ranked = sorted(((cosine(vector, c.embedding), c) for c in chunks), key=lambda pair: pair[0], reverse=True)
    return [{'id': f'D{c.pk}', 'title': c.document.title, 'text': c.text, 'score': round(score, 4), 'document_id': c.document_id, 'chunk': c.position+1} for score,c in ranked[:4] if score >= settings.RETRIEVAL_MIN_SCORE]
