from django.shortcuts import render
from django import forms
from django.conf import settings
from django.http import HttpResponse, FileResponse
from datetime import date
from decimal import Decimal
import csv
import os

from .reports import (
    obtener_eventos_por_rango,
    generar_contexto_reporte_historico,
    generar_proyeccion_json,
    resumen_proyeccion,
)
from .analytics import obtener_proyeccion_hasta_fecha
from .exports import exportar_a_excel
from .pdf import exportar_a_pdf


# ============================
# FORMULARIO DE REPORTE
# ============================

class ReporteForm(forms.Form):
    desde = forms.DateField(label="Desde", initial=date.today)
    hasta = forms.DateField(label="Hasta", initial=date.today)

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get("desde")
        hasta = cleaned_data.get("hasta")

        if desde and hasta and desde > hasta:
            raise forms.ValidationError("La fecha 'Desde' no puede ser mayor que 'Hasta'.")

        return cleaned_data


# ============================
# HELPERS
# ============================

def _normalizar_data_fechas(data):
    """
    Permite compatibilidad con templates que usen:
    - desde / hasta
    o
    - fecha_desde / fecha_hasta
    """
    mutable = data.copy()

    if 'fecha_desde' in mutable and 'desde' not in mutable:
        mutable['desde'] = mutable.get('fecha_desde')

    if 'fecha_hasta' in mutable and 'hasta' not in mutable:
        mutable['hasta'] = mutable.get('fecha_hasta')

    return mutable


def _asegurar_carpeta_reportes():
    carpeta = os.path.join(settings.MEDIA_ROOT, 'reportes')
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _exportar_csv(eventos, desde, hasta):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="reporte_{desde}_{hasta}.csv"'

    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')

    writer.writerow(['Fecha', 'Compromiso', 'Monto', 'Método', 'Observación'])

    for e in eventos:
        writer.writerow([
            e.fecha_pago.strftime('%d-%m-%Y') if e.fecha_pago else '',
            e.pago.nombre if getattr(e, 'pago', None) else '',
            str(e.monto),
            e.metodo_pago or '',
            e.observacion or '',
        ])

    return response


def _exportar_xlsx(eventos, desde, hasta):
    carpeta = _asegurar_carpeta_reportes()
    archivo = os.path.join(carpeta, f"reporte_{desde}_{hasta}.xlsx")
    exportar_a_excel(eventos, archivo)

    return FileResponse(
        open(archivo, 'rb'),
        as_attachment=True,
        filename=os.path.basename(archivo)
    )


def _exportar_pdf(eventos, total, desde, hasta):
    carpeta = _asegurar_carpeta_reportes()
    archivo = os.path.join(carpeta, f"reporte_{desde}_{hasta}.pdf")
    exportar_a_pdf(eventos, total, archivo)

    return FileResponse(
        open(archivo, 'rb'),
        as_attachment=True,
        filename=os.path.basename(archivo)
    )


# ============================
# VISTA PRINCIPAL REPORTE
# ============================

def reporte_financiero(request):
    """
    Reporte financiero histórico basado en PagoReal
    + proyección futura basada en EventoPago pendiente.
    """

    # -------------------------------------------------
    # EXPORTACIONES POR GET
    # -------------------------------------------------
    if request.method == 'GET' and request.GET.get('export'):
        export = request.GET.get('export')
        data = _normalizar_data_fechas(request.GET)
        form = ReporteForm(data)

        if form.is_valid():
            desde = form.cleaned_data['desde']
            hasta = form.cleaned_data['hasta']
            eventos = obtener_eventos_por_rango(desde, hasta)
            total = sum([Decimal(e.monto) for e in eventos], Decimal('0.00'))

            try:
                if export == 'csv':
                    return _exportar_csv(eventos, desde, hasta)

                if export == 'xlsx':
                    return _exportar_xlsx(eventos, desde, hasta)

                if export == 'pdf':
                    return _exportar_pdf(eventos, total, desde, hasta)

            except Exception as e:
                print(f"Error exportando {export}: {e}")

    # -------------------------------------------------
    # CONTEXTO BASE
    # -------------------------------------------------
    context = {
        'eventos': [],
        'total': Decimal('0.00'),
        'promedio': Decimal('0.00'),
        'metodo_principal': '—',
        'top_compromisos': [],
        'chart_diario_json': '{"labels":[],"valores":[]}',
        'chart_metodo_json': '{"labels":[],"valores":[]}',
        'proyeccion_json': '{"labels":[],"valores":[],"acumulado":[]}',
        'proyeccion_data': None,
        'proyeccion_tabla': [],
        'desde': None,
        'hasta': None,
    }

    # -------------------------------------------------
    # RENDER NORMAL
    # -------------------------------------------------
    if request.method == 'POST':
        data = _normalizar_data_fechas(request.POST)
        form = ReporteForm(data)

        if form.is_valid():
            desde = form.cleaned_data['desde']
            hasta = form.cleaned_data['hasta']

            # Histórico real
            contexto_reporte = generar_contexto_reporte_historico(desde, hasta)
            context.update(contexto_reporte)

            # Proyección futura hasta la misma fecha "hasta"
            fecha_proyeccion = hasta
            proyeccion_json = generar_proyeccion_json(fecha_proyeccion)
            resumen_proj = resumen_proyeccion(fecha_proyeccion)
            proyeccion_tabla = obtener_proyeccion_hasta_fecha(fecha_proyeccion)

            context.update({
                'proyeccion_json': proyeccion_json,
                'proyeccion_data': resumen_proj,
                'proyeccion_tabla': proyeccion_tabla,
            })

    else:
        form = ReporteForm()

    context['form'] = form

    return render(request, 'pagos/reportes.html', context)