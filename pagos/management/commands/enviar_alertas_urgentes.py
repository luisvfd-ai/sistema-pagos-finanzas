from django.core.management.base import BaseCommand
from django.conf import settings

from pagos.views_dashboard import _enviar_alerta_urgente_email_base


class Command(BaseCommand):
    help = 'Envía por correo las alertas financieras urgentes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--forzar',
            action='store_true',
            help='Envía aunque ALERTAS_AUTOMATICAS_ACTIVAS esté desactivado.'
        )

    def handle(self, *args, **options):
        forzar = options.get('forzar', False)

        if not forzar and not getattr(settings, 'ALERTAS_AUTOMATICAS_ACTIVAS', True):
            self.stdout.write(
                self.style.WARNING('Las alertas automáticas están desactivadas en settings.')
            )
            return

        try:
            resultado = _enviar_alerta_urgente_email_base()

            if resultado['ok'] and resultado['enviado']:
                self.stdout.write(self.style.SUCCESS(resultado['mensaje']))
            elif resultado['ok'] and not resultado['enviado']:
                self.stdout.write(self.style.WARNING(resultado['mensaje']))
            else:
                self.stdout.write(self.style.ERROR(resultado['mensaje']))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al enviar alertas: {e}'))
            raise