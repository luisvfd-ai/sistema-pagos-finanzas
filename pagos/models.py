from decimal import Decimal
import hashlib

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify


LEGACY_UNIDAD_NEGOCIO_CHOICES = [
    ('terminal', 'Terminal'),
    ('cauquenes', 'Cauquenes'),
    ('alerce', 'Alerce'),
    ('pitrufquen', 'Pitrufquén'),
    ('pasmar', 'Pasmar'),
    ('valdivia', 'Valdivia'),
    ('espacio_costanera', 'Espacio Costanera'),
    ('costanera_ampliacion', 'Costanera Ampliación'),
    ('mall_castro', 'Mall Castro'),
    ('carolina', 'Carolina'),
    ('oficina', 'Oficina'),
    ('imposiciones', 'Imposiciones'),
    ('iva', 'IVA'),
    ('vivian', 'Vivian'),
    ('tottus', 'Tottus'),
    ('otros', 'Otros'),
]


def _normalizar_codigo_unidad(raw: str) -> str:
    raw = (raw or '').strip().lower().replace('-', '_').replace(' ', '_')
    if not raw:
        return 'otros'
    return slugify(raw).replace('-', '_') or 'otros'


def unidad_negocio_label_from_codigo(codigo: str) -> str:
    codigo = _normalizar_codigo_unidad(codigo)
    try:
        unidad = UnidadNegocio.objects.filter(codigo=codigo).first()
        if unidad:
            return unidad.nombre
    except Exception:
        pass

    mapa = dict(LEGACY_UNIDAD_NEGOCIO_CHOICES)
    if codigo in mapa:
        return mapa[codigo]

    return codigo.replace('_', ' ').strip().title() or 'Otros'


def unidades_negocio_disponibles(incluir_inactivas: bool = False):
    try:
        qs = UnidadNegocio.objects.all().order_by('orden', 'nombre', 'id')
        if not incluir_inactivas:
            qs = qs.filter(activa=True)

        data = [
            {'value': u.codigo, 'label': u.nombre}
            for u in qs
        ]

        if not data:
            return [
                {'value': value, 'label': label}
                for value, label in LEGACY_UNIDAD_NEGOCIO_CHOICES
            ]

        if not any(item['value'] == 'otros' for item in data):
            data.append({'value': 'otros', 'label': 'Otros'})

        return data
    except Exception:
        return [
            {'value': value, 'label': label}
            for value, label in LEGACY_UNIDAD_NEGOCIO_CHOICES
        ]


class UnidadNegocio(models.Model):
    nombre = models.CharField(max_length=120)
    codigo = models.SlugField(max_length=40, unique=True)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)
    legacy_key = models.CharField(max_length=40, blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['orden', 'nombre', 'id']
        verbose_name = 'Unidad de negocio'
        verbose_name_plural = 'Unidades de negocio'

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        old_codigo = None
        if self.pk:
            old_codigo = UnidadNegocio.objects.filter(pk=self.pk).values_list('codigo', flat=True).first()

        self.nombre = (self.nombre or '').strip() or 'Unidad'
        self.codigo = _normalizar_codigo_unidad(self.codigo or self.nombre)
        self.legacy_key = (self.legacy_key or self.codigo or '').strip()

        super().save(*args, **kwargs)

        if old_codigo != self.codigo:
            try:
                PagoProgramado.objects.filter(unidad_negocio_ref=self).update(unidad_negocio=self.codigo)
            except Exception:
                pass

    @property
    def total_compromisos(self):
        try:
            return self.pagos_programados.count()
        except Exception:
            return 0


class EmpresaConfig(models.Model):
    config_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    nombre_empresa = models.CharField(max_length=160, default='Mi empresa')
    razon_social = models.CharField(max_length=180, blank=True, default='')
    rut = models.CharField(max_length=20, blank=True, default='')
    giro = models.CharField(max_length=180, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    telefono = models.CharField(max_length=40, blank=True, default='')
    direccion = models.CharField(max_length=220, blank=True, default='')
    ciudad = models.CharField(max_length=120, blank=True, default='')
    logo = models.FileField(
        upload_to='empresa/logos/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'svg', 'webp'])],
        verbose_name='Logo',
        help_text='Formatos permitidos: PNG, JPG, JPEG, SVG o WEBP.'
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Configuración de empresa'
        verbose_name_plural = 'Configuración de empresa'

    def __str__(self):
        return self.nombre_empresa or self.razon_social or 'Empresa'

    @classmethod
    def get_solo(cls):
        return cls.objects.order_by('id').first()

    @property
    def display_name(self):
        return (self.nombre_empresa or self.razon_social or 'Finanzas').strip()

    def save(self, *args, **kwargs):
        self.config_key = 1
        self.nombre_empresa = (self.nombre_empresa or '').strip() or 'Mi empresa'
        self.razon_social = (self.razon_social or '').strip()
        self.rut = (self.rut or '').strip()
        self.giro = (self.giro or '').strip()
        self.email = (self.email or '').strip()
        self.telefono = (self.telefono or '').strip()
        self.direccion = (self.direccion or '').strip()
        self.ciudad = (self.ciudad or '').strip()
        super().save(*args, **kwargs)


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

    UNIDAD_NEGOCIO_CHOICES = LEGACY_UNIDAD_NEGOCIO_CHOICES

    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=12, decimal_places=0)
    fecha_inicio = models.DateField()
    frecuencia = models.CharField(max_length=20, choices=FRECUENCIA_CHOICES)
    total_cuotas = models.PositiveIntegerField()
    cuotas_restantes = models.PositiveIntegerField()
    descripcion = models.TextField(blank=True)
    unidad_negocio_ref = models.ForeignKey(
        UnidadNegocio,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='pagos_programados',
        verbose_name='Unidad / lugar'
    )
    unidad_negocio = models.CharField(
        max_length=40,
        choices=UNIDAD_NEGOCIO_CHOICES,
        default='otros',
        blank=True,
        verbose_name='Unidad / lugar'
    )
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - ${self.monto}"

    @classmethod
    def unidades_negocio_disponibles(cls, incluir_inactivas: bool = False):
        return unidades_negocio_disponibles(incluir_inactivas=incluir_inactivas)

    def unidad_negocio_codigo_actual(self):
        if getattr(self, 'unidad_negocio_ref_id', None) and getattr(self, 'unidad_negocio_ref', None):
            return self.unidad_negocio_ref.codigo or 'otros'
        return _normalizar_codigo_unidad(self.unidad_negocio or 'otros')

    def unidad_negocio_label_actual(self):
        if getattr(self, 'unidad_negocio_ref_id', None) and getattr(self, 'unidad_negocio_ref', None):
            return self.unidad_negocio_ref.nombre or 'Otros'
        return unidad_negocio_label_from_codigo(self.unidad_negocio or 'otros')

    def save(self, *args, **kwargs):
        codigo = _normalizar_codigo_unidad(self.unidad_negocio or 'otros')

        if self.unidad_negocio_ref_id and getattr(self, 'unidad_negocio_ref', None):
            codigo = self.unidad_negocio_ref.codigo or codigo or 'otros'
        else:
            try:
                unidad = UnidadNegocio.objects.filter(codigo=codigo).first()
                if unidad:
                    self.unidad_negocio_ref = unidad
            except Exception:
                pass

        self.unidad_negocio = codigo or 'otros'
        super().save(*args, **kwargs)

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

    descripcion = models.CharField(max_length=180, blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Importación #{self.importacion_id} - {self.tipo_registro} - fila {self.fila_excel or '-'}"


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

    cuenta = models.CharField(max_length=80, blank=True, default='')
    banco = models.CharField(max_length=80, blank=True, default='')
    fecha = models.DateField()
    descripcion = models.CharField(max_length=255)
    referencia = models.CharField(max_length=120, blank=True, default='')

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='desconocido')
    monto = models.DecimalField(max_digits=14, decimal_places=2)

    moneda = models.CharField(max_length=10, default='CLP')
    hash_unico = models.CharField(max_length=64, unique=True)

    raw = models.JSONField(default=dict, blank=True)

    conciliado = models.BooleanField(default=False)
    pago_real = models.ForeignKey(
        PagoReal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_conciliados'
    )
    conciliado_en = models.DateTimeField(null=True, blank=True)
    nota_conciliacion = models.CharField(max_length=255, blank=True, default='')

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
    def build_hash(fecha, monto, descripcion, referencia='', cuenta=''):
        base = f"{fecha}|{monto}|{(descripcion or '').strip().lower()}|{(referencia or '').strip().lower()}|{(cuenta or '').strip().lower()}"
        return hashlib.sha256(base.encode('utf-8')).hexdigest()

    def marcar_conciliado(self, pago_real: PagoReal, nota: str = ''):
        self.pago_real = pago_real
        self.conciliado = True
        self.conciliado_en = timezone.now()
        self.nota_conciliacion = (nota or '').strip()[:255]
        self.save(update_fields=['pago_real', 'conciliado', 'conciliado_en', 'nota_conciliacion'])

    def desconciliar(self):
        self.pago_real = None
        self.conciliado = False
        self.conciliado_en = None
        self.nota_conciliacion = ''
        self.save(update_fields=['pago_real', 'conciliado', 'conciliado_en', 'nota_conciliacion'])
