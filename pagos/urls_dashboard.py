from django.urls import path
from . import views_dashboard
from .views_api import api_pago_info

urlpatterns = [
    path('dashboard/', views_dashboard.dashboard_financiero, name='dashboard_financiero'),
    path('alertas/', views_dashboard.alertas_financieras, name='alertas_financieras'),
    path('alertas/enviar-email/', views_dashboard.enviar_alerta_urgente_email, name='enviar_alerta_urgente_email'),

    path('pagos/', views_dashboard.pagos_lista, name='pagos_lista'),
    path('pagos/nuevo/', views_dashboard.pagos_crear, name='pagos_crear'),
    path('pagos/importar-excel/', views_dashboard.pagos_importar_excel, name='pagos_importar_excel'),
    path('pagos/importar-excel/confirmar/', views_dashboard.pagos_importar_excel_confirmar, name='pagos_importar_excel_confirmar'),
    path('pagos/importar-excel/limpiar-preview/', views_dashboard.pagos_importar_excel_limpiar_preview, name='pagos_importar_excel_limpiar_preview'),
    path('pagos/importaciones/historial/', views_dashboard.importaciones_historial, name='importaciones_historial'),
    path('pagos/importaciones/<int:pk>/revertir/', views_dashboard.importacion_revertir, name='importacion_revertir'),
    path('pagos/descargar/plantilla/', views_dashboard.descargar_plantilla_importacion, name='descargar_plantilla_importacion'),
    path('pagos/descargar/guia/', views_dashboard.descargar_guia_importacion, name='descargar_guia_importacion'),
    path('pagos/<int:pk>/editar/', views_dashboard.pagos_editar, name='pagos_editar'),
    path('pagos/real/nuevo/', views_dashboard.pagos_real_crear, name='pagos_real_crear'),
    path('pagos/real/<int:pk>/editar/', views_dashboard.pagos_real_editar, name='pagos_real_editar'),

    path('empresa/', views_dashboard.empresa_configuracion, name='empresa_configuracion'),
    path('ayuda/', views_dashboard.ayuda, name='ayuda'),

    path('unidades/', views_dashboard.unidades_negocio_lista, name='unidades_negocio_lista'),
    path('unidades/nueva/', views_dashboard.unidades_negocio_crear, name='unidades_negocio_crear'),
    path('unidades/<int:pk>/editar/', views_dashboard.unidades_negocio_editar, name='unidades_negocio_editar'),
    path('unidades/<int:pk>/toggle/', views_dashboard.unidades_negocio_toggle, name='unidades_negocio_toggle'),
    path('unidades/<int:pk>/eliminar/', views_dashboard.unidades_negocio_eliminar, name='unidades_negocio_eliminar'),

    path('reportes/', views_dashboard.reportes_financieros, name='reportes_financieros'),

    path('cartolas/', views_dashboard.cartolas_lista, name='cartolas_lista'),
    path('cartolas/importar/', views_dashboard.cartolas_importar, name='cartolas_importar'),
    path('cartolas/sugerencias/', views_dashboard.cartolas_sugerencias, name='cartolas_sugerencias'),

    path('conciliacion/', views_dashboard.conciliacion_panel, name='conciliacion_panel'),
    path('cartolas/auto-conciliar/', views_dashboard.cartolas_auto_conciliar, name='cartolas_auto_conciliar'),
    path('cartolas/conciliar/', views_dashboard.cartolas_conciliar, name='cartolas_conciliar'),
    path('cartolas/desconciliar/<int:mov_id>/', views_dashboard.cartolas_desconciliar, name='cartolas_desconciliar'),

    path('api/pago-info/<int:pk>/', api_pago_info, name='api_pago_info'),
]