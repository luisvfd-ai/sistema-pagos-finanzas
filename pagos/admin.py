from django.contrib import admin
from .models import (
    PagoProgramado,
    EventoPago,
    PagoReal,
    ImportacionPago,
    ImportacionPagoDetalle,
)


@admin.register(PagoProgramado)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'monto', 'frecuencia', 'fecha_inicio', 'activo')
    list_filter = ('tipo', 'frecuencia', 'activo')
    search_fields = ('nombre',)


@admin.register(EventoPago)
class EventoPagoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'pago', 'monto', 'estado')
    list_filter = ('estado', 'fecha')
    search_fields = ('pago__nombre',)


@admin.register(PagoReal)
class PagoRealAdmin(admin.ModelAdmin):
    list_display = ('fecha_pago', 'pago', 'monto', 'metodo_pago')
    list_filter = ('metodo_pago', 'fecha_pago')
    search_fields = ('pago__nombre', 'observacion')


class ImportacionPagoDetalleInline(admin.TabularInline):
    model = ImportacionPagoDetalle
    extra = 0
    readonly_fields = ('fila_excel', 'tipo_registro', 'pago_programado', 'pago_real', 'descripcion', 'creado')
    can_delete = False


@admin.register(ImportacionPago)
class ImportacionPagoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'archivo_nombre',
        'usuario',
        'creado',
        'estado',
        'total_deudas_creadas',
        'total_pagos_creados',
        'total_errores',
    )
    list_filter = ('estado', 'crear_pagos_reales', 'creado')
    search_fields = ('archivo_nombre', 'usuario__username', 'usuario__email')
    readonly_fields = (
        'usuario',
        'archivo_nombre',
        'hoja',
        'crear_pagos_reales',
        'resumen',
        'total_deudas_creadas',
        'total_deudas_existentes',
        'total_pagos_creados',
        'total_pagos_existentes',
        'total_omitidas',
        'total_errores',
        'estado',
        'revertida_en',
        'revertida_por',
        'creado',
    )
    inlines = [ImportacionPagoDetalleInline]


@admin.register(ImportacionPagoDetalle)
class ImportacionPagoDetalleAdmin(admin.ModelAdmin):
    list_display = ('id', 'importacion', 'fila_excel', 'tipo_registro', 'pago_programado', 'pago_real', 'creado')
    list_filter = ('tipo_registro', 'creado')
    search_fields = ('descripcion', 'importacion__archivo_nombre')