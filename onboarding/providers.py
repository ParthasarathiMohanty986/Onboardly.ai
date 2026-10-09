import json
import math
import urllib.error
import urllib.request
from django.conf import settings

class AIError(Exception):
    pass

def request(path, payload=None):
    req = urllib.request.Request(settings.OLLAMA_URL.rstrip('/') + path, data=json.dumps(payload).encode() if payload is not None else None, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=settings.AI_REQUEST_TIMEOUT) as response:
            result = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise AIError('Ollama is unavailable, timed out, or a model is missing. Check the service and installed models.') from exc
    if not isinstance(result, dict) or result.get('error'): raise AIError('Ollama returned an invalid response.')
    return result

def chat_completion(messages, tools):
    result = request('/api/chat', {'model': settings.OLLAMA_MODEL, 'messages': messages, 'tools': tools, 'stream': False, 'think': False, 'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 1400}})
    message = result.get('message')
    if not isinstance(message, dict) or message.get('role') != 'assistant': raise AIError('Invalid chat response.')
    return message

def embed(texts):
    result = request('/api/embed', {'model': settings.OLLAMA_EMBED_MODEL, 'input': texts, 'truncate': False})
    vectors = result.get('embeddings')
    if not isinstance(vectors, list) or len(vectors) != len(texts): raise AIError('Invalid embedding response.')
    dimension = None
    for vector in vectors:
        if not isinstance(vector, list) or not vector or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in vector): raise AIError('Invalid embedding values.')
        if dimension is None: dimension = len(vector)
        if len(vector) != dimension or not sum(n*n for n in vector): raise AIError('Invalid embedding dimensions.')
    return vectors
