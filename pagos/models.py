from decimal import Decimal
import hashlib

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class PagoProgramado(models.Model):

    TIPO_CHOICES = [
        ('credito', 'Crédito'),
        ('cuota', 'Cuota tienda'),
        ('fijo', 'Pago fijo'),
        ('cheque', 'Cheque a fecha'),
        ('unico', 'Pago único'),
    ]

    FRECUENCIA_CHOICES = [
        ('mensual', 'Mensual'),
        ('quincenal', 'Quincenal'),
        ('semanal', 'Semanal'),
        ('unico', 'Único'),
    ]

    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=12, decimal_places=0)
    fecha_inicio = models.DateField()
    frecuencia = models.CharField(max_length=20, choices=FRECUENCIA_CHOICES)
    total_cuotas = models.PositiveIntegerField()
    cuotas_restantes = models.PositiveIntegerField()
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - ${self.monto}"

    def total_pagado(self, excluir_pago_real_id=None):
        pagos_qs = self.pagos_realizados.all()
        if excluir_pago_real_id:
            pagos_qs = pagos_qs.exclude(pk=excluir_pago_real_id)
        return pagos_qs.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    def total_compromiso(self):
        total_eventos = self.eventos.aggregate(total=Sum('monto'))['total']
        if total_eventos is None:
            return Decimal(self.total_cuotas or 0) * Decimal(self.monto or 0)
        return Decimal(total_eventos or 0)

    def total_pendiente_eventos(self):
        total_pendiente = self.eventos.filter(estado='pendiente').aggregate(total=Sum('monto'))['total']
        if total_pendiente is None:
            return Decimal(self.cuotas_restantes or 0) * Decimal(self.monto or 0)
        return Decimal(total_pendiente or 0)

    def saldo_pendiente_real(self, excluir_pago_real_id=None):
        saldo = self.total_compromiso() - self.total_pagado(excluir_pago_real_id=excluir_pago_real_id)
        if saldo < 0:
            return Decimal('0.00')
        return saldo

    def saldo_pendiente(self):
        return self.saldo_pendiente_real()

    def estado_real(self):
        if self.saldo_pendiente_real() <= 0:
            return 'PAGADO'
        elif self.total_pagado() > 0:
            return 'PARCIAL'
        return 'PENDIENTE'

    def porcentaje_pagado(self):
        total = self.total_compromiso()
        if total <= 0:
            return 0
        return round((self.total_pagado() / total) * 100, 2)


class EventoPago(models.Model):

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
    ]

    pago = models.ForeignKey(
        PagoProgramado,
        on_delete=models.CASCADE,
        related_name='eventos'
    )

    fecha = models.DateField()
    monto = models.DecimalField(max_digits=12, decimal_places=0)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fecha} - {self.pago.nombre}"

    def saldo_pendiente_real(self):
        return self.pago.saldo_pendiente_real()


class PagoReal(models.Model):

    METODO_PAGO_CHOICES = (
        ('transferencia', 'Transferencia'),
        ('debito', 'Débito'),
        ('credito', 'Crédito'),
        ('efectivo', 'Efectivo'),
        ('cheque', 'Cheque'),
    )

    pago = models.ForeignKey(
        PagoProgramado,
        on_delete=models.CASCADE,
        related_name='pagos_realizados'
    )

    fecha_pago = models.DateField()
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    observacion = models.TextField(blank=True, null=True)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_pago']

    def __str__(self):
        return f"{self.pago.nombre} - ${self.monto} ({self.fecha_pago})"


# ==================================================
# HISTORIAL DE IMPORTACIONES
# ==================================================

class ImportacionPago(models.Model):

    ESTADO_CHOICES = [
        ('confirmada', 'Confirmada'),
        ('revertida', 'Revertida'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='importaciones_pagos'
    )

    archivo_nombre = models.CharField(max_length=255)
    hoja = models.CharField(max_length=120, blank=True)
    crear_pagos_reales = models.BooleanField(default=False)

    resumen = models.JSONField(default=dict, blank=True)

    total_deudas_creadas = models.PositiveIntegerField(default=0)
    total_deudas_existentes = models.PositiveIntegerField(default=0)
    total_pagos_creados = models.PositiveIntegerField(default=0)
    total_pagos_existentes = models.PositiveIntegerField(default=0)
    total_omitidas = models.PositiveIntegerField(default=0)
    total_errores = models.PositiveIntegerField(default=0)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='confirmada')

    revertida_en = models.DateTimeField(null=True, blank=True)
    revertida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='importaciones_pagos_revertidas'
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return f"Importación #{self.id} - {self.archivo_nombre}"

    def total_registros_creados(self):
        return self.total_deudas_creadas + self.total_pagos_creados

    def puede_revertirse(self):
        return self.estado == 'confirmada'


class ImportacionPagoDetalle(models.Model):

    TIPO_REGISTRO_CHOICES = [
        ('deuda', 'Deuda creada'),
        ('pago_real', 'Pago real creado'),
    ]

    importacion = models.ForeignKey(
        ImportacionPago,
        on_delete=models.CASCADE,
        related_name='detalles'
    )

    fila_excel = models.PositiveIntegerField(null=True, blank=True)
    tipo_registro = models.CharField(max_length=20, choices=TIPO_REGISTRO_CHOICES)

    pago_programado = models.ForeignKey(
        PagoProgramado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detalles_importacion'
    )

    pago_real = models.ForeignKey(
        PagoReal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detalles_importacion'
    )

    descripcion = models.CharField(max_length=180, blank=True, default="")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Importación #{self.importacion_id} - {self.tipo_registro} - fila {self.fila_excel or '-'}"


# ==================================================
# MOVIMIENTOS BANCARIOS (CARTOLAS) + CONCILIACIÓN
# ==================================================

class MovimientoBancario(models.Model):
    """
    Registro histórico de cartolas bancarias.
    - Import CSV/XLSX
    - Deduplicación por hash estable
    - Conciliación: vincular MovimientoBancario -> PagoReal
    """

    TIPO_CHOICES = (
        ('cargo', 'Cargo / Salida'),
        ('abono', 'Abono / Entrada'),
        ('desconocido', 'Desconocido'),
    )

    cuenta = models.CharField(max_length=80, blank=True, default="")
    banco = models.CharField(max_length=80, blank=True, default="")
    fecha = models.DateField()
    descripcion = models.CharField(max_length=255)
    referencia = models.CharField(max_length=120, blank=True, default="")

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='desconocido')
    monto = models.DecimalField(max_digits=14, decimal_places=2)

    moneda = models.CharField(max_length=10, default="CLP")
    hash_unico = models.CharField(max_length=64, unique=True)

    raw = models.JSONField(default=dict, blank=True)

    conciliado = models.BooleanField(default=False)
    pago_real = models.ForeignKey(
        PagoReal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_conciliados"
    )
    conciliado_en = models.DateTimeField(null=True, blank=True)
    nota_conciliacion = models.CharField(max_length=255, blank=True, default="")

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['monto']),
            models.Index(fields=['tipo']),
            models.Index(fields=['conciliado']),
        ]

    def __str__(self):
        return f"{self.fecha} {self.descripcion} {self.monto}"

    @staticmethod
    def build_hash(fecha, monto, descripcion, referencia="", cuenta=""):
        base = f"{fecha}|{monto}|{(descripcion or '').strip().lower()}|{(referencia or '').strip().lower()}|{(cuenta or '').strip().lower()}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def marcar_conciliado(self, pago_real: PagoReal, nota: str = ""):
        self.pago_real = pago_real
        self.conciliado = True
        self.conciliado_en = timezone.now()
        self.nota_conciliacion = (nota or "").strip()[:255]
        self.save(update_fields=["pago_real", "conciliado", "conciliado_en", "nota_conciliacion"])

    def desconciliar(self):
        self.pago_real = None
        self.conciliado = False
        self.conciliado_en = None
        self.nota_conciliacion = ""
        self.save(update_fields=["pago_real", "conciliado", "conciliado_en", "nota_conciliacion"])
