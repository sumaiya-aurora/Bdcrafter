from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Deprecated: dummy product data is no longer loaded'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'Dummy product loading is disabled. Use load_fragrance_catalog instead.'
        ))
