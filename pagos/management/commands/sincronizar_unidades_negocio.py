from django.core.management.base import BaseCommand
from django.db import transaction

from pagos.models import PagoProgramado, UnidadNegocio, LEGACY_UNIDAD_NEGOCIO_CHOICES, unidad_negocio_label_from_codigo


class Command(BaseCommand):
    help = 'Crea unidades de negocio desde valores legacy y vincula los PagoProgramado existentes.'

    @transaction.atomic
    def handle(self, *args, **options):
        legacy_map = dict(LEGACY_UNIDAD_NEGOCIO_CHOICES)
        legacy_order = {codigo: idx for idx, (codigo, _label) in enumerate(LEGACY_UNIDAD_NEGOCIO_CHOICES, start=1)}

        codigos = {codigo for codigo, _ in LEGACY_UNIDAD_NEGOCIO_CHOICES}
        codigos.update(
            (c or 'otros').strip()
            for c in PagoProgramado.objects.values_list('unidad_negocio', flat=True).distinct()
            if (c or '').strip()
        )

        unidades = {}
        creadas = 0
        actualizadas = 0

        for codigo in sorted(codigos):
            codigo = (codigo or 'otros').strip()
            nombre = legacy_map.get(codigo) or unidad_negocio_label_from_codigo(codigo)
            defaults = {
                'nombre': nombre,
                'legacy_key': codigo,
                'orden': legacy_order.get(codigo, 999),
                'activa': True,
            }
            unidad, created = UnidadNegocio.objects.get_or_create(codigo=codigo, defaults=defaults)
            if created:
                creadas += 1
            else:
                changed = False
                if not unidad.nombre:
                    unidad.nombre = nombre
                    changed = True
                if not unidad.legacy_key:
                    unidad.legacy_key = codigo
                    changed = True
                if changed:
                    unidad.save()
                    actualizadas += 1
            unidades[codigo] = unidad

        vinculadas = 0
        for pago in PagoProgramado.objects.select_related('unidad_negocio_ref').all():
            codigo = (pago.unidad_negocio or '').strip()
            if not codigo and pago.unidad_negocio_ref_id:
                codigo = pago.unidad_negocio_ref.codigo
            if not codigo:
                codigo = 'otros'

            unidad = unidades.get(codigo)
            if not unidad:
                unidad = UnidadNegocio.objects.create(
                    codigo=codigo,
                    nombre=unidad_negocio_label_from_codigo(codigo),
                    legacy_key=codigo,
                    orden=999,
                    activa=True,
                )
                unidades[codigo] = unidad
                creadas += 1

            changed = False
            if pago.unidad_negocio_ref_id != unidad.id:
                pago.unidad_negocio_ref = unidad
                changed = True
            if pago.unidad_negocio != unidad.codigo:
                pago.unidad_negocio = unidad.codigo
                changed = True

            if changed:
                pago.save(update_fields=['unidad_negocio_ref', 'unidad_negocio'])
                vinculadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'Unidades creadas: {creadas} | actualizadas: {actualizadas} | pagos vinculados: {vinculadas}'
        ))
