from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from onboarding.retrieval import index_document
from onboarding.providers import AIError

class Command(BaseCommand):
    help = 'Embed and index agency Markdown/text documents through Ollama.'
    def add_arguments(self, parser): parser.add_argument('--directory', default=str(settings.BASE_DIR / 'knowledge'))
    def handle(self, *args, **options):
        files = sorted(p for p in Path(options['directory']).glob('*') if p.suffix in {'.md', '.txt'})
        if not files: raise CommandError('No .md or .txt documents found.')
        for path in files:
            try: doc = index_document(path.stem.replace('_', ' ').title(), path.read_text(encoding='utf-8'))
            except (AIError, ValueError) as exc: raise CommandError(str(exc)) from exc
            self.stdout.write(f'Indexed {doc.title}: {doc.chunks.count()} chunks')
