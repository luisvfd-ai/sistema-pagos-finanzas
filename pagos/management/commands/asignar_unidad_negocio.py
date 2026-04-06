from django.core.management.base import BaseCommand
from django.db import transaction

from pagos.models import PagoProgramado


class Command(BaseCommand):
    help = "Asigna unidad_negocio automáticamente según palabras clave en nombre y descripción."

    PRIORIDAD_REGLAS = [
        ("costanera_ampliacion", ["costanera ampliacion", "costanera ampliación"]),
        ("espacio_costanera", ["espacio costanera"]),
        ("mall_castro", ["mall castro", "castro"]),
        ("carolina", ["carolina"]),
        ("oficina", ["oficina"]),
        ("pitrufquen", ["pitrufquen", "pitrufquén"]),
        ("cauquenes", ["cauquenes"]),
        ("alerce", ["alerce"]),
        ("terminal", ["terminal"]),
        ("pasmar", ["pasmar"]),
        ("valdivia", ["valdivia"]),
        ("imposiciones", ["imposiciones"]),
        ("iva", ["iva"]),
        ("tottus", ["tottus"]),
        ("vivian", ["vivian"]),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Solo muestra qué cambios haría, sin guardar.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica los cambios en la base de datos.",
        )
        parser.add_argument(
            "--solo-vacios",
            action="store_true",
            help="Solo actualiza registros con unidad_negocio vacío o 'otros'.",
        )

    def _normalizar_texto(self, texto):
        return (texto or "").strip().lower()

    def _detectar_unidad(self, pago):
        nombre = self._normalizar_texto(pago.nombre)
        descripcion = self._normalizar_texto(pago.descripcion)
        texto = f"{nombre} {descripcion}".strip()

        for unidad, palabras in self.PRIORIDAD_REGLAS:
            if any(p in texto for p in palabras):
                return unidad

        return "otros"

    def handle(self, *args, **options):
        preview = options["preview"]
        apply_changes = options["apply"]
        solo_vacios = options["solo_vacios"]

        if not preview and not apply_changes:
            self.stdout.write(self.style.WARNING(
                "Debes usar una opción: --preview o --apply"
            ))
            return

        qs = PagoProgramado.objects.all().order_by("id")

        if solo_vacios:
            qs = qs.filter(unidad_negocio__in=["", "otros"])

        total = qs.count()
        cambios = []
        sin_cambio = 0

        for pago in qs:
            unidad_detectada = self._detectar_unidad(pago)
            unidad_actual = (pago.unidad_negocio or "").strip() or "otros"

            if unidad_actual != unidad_detectada:
                cambios.append({
                    "id": pago.id,
                    "nombre": pago.nombre,
                    "actual": unidad_actual,
                    "nuevo": unidad_detectada,
                })
            else:
                sin_cambio += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== RESULTADO DEL ANÁLISIS ==="))
        self.stdout.write(f"Total revisados: {total}")
        self.stdout.write(f"Con cambio sugerido: {len(cambios)}")
        self.stdout.write(f"Sin cambio: {sin_cambio}")
        self.stdout.write("")

        if cambios:
            self.stdout.write(self.style.SUCCESS("=== CAMBIOS DETECTADOS ==="))
            for item in cambios:
                self.stdout.write(
                    f"[{item['id']}] {item['nombre']} | "
                    f"{item['actual']} -> {item['nuevo']}"
                )
        else:
            self.stdout.write("No se detectaron cambios.")
            return

        if preview:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Vista previa completada. No se guardó ningún cambio."
            ))
            return

        if apply_changes:
            with transaction.atomic():
                for item in cambios:
                    PagoProgramado.objects.filter(id=item["id"]).update(
                        unidad_negocio=item["nuevo"]
                    )

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"Cambios aplicados correctamente: {len(cambios)} registro(s)."
            ))