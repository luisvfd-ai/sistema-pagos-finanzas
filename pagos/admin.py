from django.contrib import admin
from .models import (
    EmpresaConfig,
    UnidadNegocio,
    PagoProgramado,
    EventoPago,
    PagoReal,
    ImportacionPago,
    ImportacionPagoDetalle,
)


@admin.register(EmpresaConfig)
class EmpresaConfigAdmin(admin.ModelAdmin):
    list_display = ('display_name_admin', 'rut', 'ciudad', 'email', 'telefono', 'actualizado')
    readonly_fields = ('config_key', 'creado', 'actualizado')

    fieldsets = (
        ('Identificación', {
            'fields': ('nombre_empresa', 'razon_social', 'rut', 'giro')
        }),
        ('Contacto', {
            'fields': ('email', 'telefono', 'direccion', 'ciudad')
        }),
        ('Branding', {
            'fields': ('logo',)
        }),
        ('Sistema', {
            'fields': ('config_key', 'creado', 'actualizado')
        }),
    )

    @admin.display(description='Empresa')
    def display_name_admin(self, obj):
        return obj.display_name

    def has_add_permission(self, request):
        if EmpresaConfig.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(UnidadNegocio)
class UnidadNegocioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'activa', 'orden', 'total_compromisos')
    list_filter = ('activa',)
    search_fields = ('nombre', 'codigo', 'descripcion')
    ordering = ('orden', 'nombre')


@admin.register(PagoProgramado)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre',
        'tipo',
        'unidad_negocio_label_admin',
        'monto',
        'frecuencia',
        'fecha_inicio',
        'activo',
    )
    list_filter = ('tipo', 'unidad_negocio_ref', 'frecuencia', 'activo')
    search_fields = ('nombre', 'descripcion', 'unidad_negocio')

    @admin.display(description='Unidad')
    def unidad_negocio_label_admin(self, obj):
        return obj.unidad_negocio_label_actual()


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
