from django.shortcuts import render
from django import forms
from django.conf import settings
from datetime import date
from decimal import Decimal
import os

from .reports import obtener_eventos_por_rango
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
# VISTA PRINCIPAL REPORTE
# ============================

def reporte_financiero(request):
    """
    Genera reportes financieros entre dos fechas:
    - Lista eventos
    - Calcula total
    - Exporta Excel
    - Exporta PDF
    """

    eventos = []
    total = Decimal('0.00')
    archivo_excel = None
    archivo_pdf = None

    if request.method == 'POST':
        form = ReporteForm(request.POST)

        if form.is_valid():
            desde = form.cleaned_data['desde']
            hasta = form.cleaned_data['hasta']

            eventos = obtener_eventos_por_rango(desde, hasta)

            # Calcular total financiero
            total = sum([Decimal(e.monto) for e in eventos], Decimal('0.00'))

            # Crear carpeta de reportes dentro de MEDIA_ROOT
            carpeta = os.path.join(settings.MEDIA_ROOT, 'reportes')
            os.makedirs(carpeta, exist_ok=True)

            nombre_base = f"reporte_{desde}_{hasta}"

            archivo_excel = os.path.join(carpeta, f"{nombre_base}.xlsx")
            archivo_pdf = os.path.join(carpeta, f"{nombre_base}.pdf")

            # Exportaciones protegidas
            try:
                exportar_a_excel(eventos, archivo_excel)
            except Exception as e:
                print(f"Error generando Excel: {e}")
                archivo_excel = None

            try:
                exportar_a_pdf(eventos, total, archivo_pdf)
            except Exception as e:
                print(f"Error generando PDF: {e}")
                archivo_pdf = None

    else:
        form = ReporteForm()

    return render(request, 'pagos/reportes.html', {
        'form': form,
        'eventos': eventos,
        'total': total,
        'excel': archivo_excel,
        'pdf': archivo_pdf
    })
