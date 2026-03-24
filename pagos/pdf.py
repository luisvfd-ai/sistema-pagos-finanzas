from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from datetime import datetime


# ============================
# EXPORTACIÓN PDF EJECUTIVO
# ============================

def exportar_a_pdf(eventos, total, ruta):
    """
    Genera un reporte financiero ejecutivo en PDF,
    optimizado para gerencia y toma de decisiones.
    """

    c = canvas.Canvas(ruta, pagesize=A4)
    width, height = A4

    y = height - 2 * cm

    # Encabezado
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "REPORTE FINANCIERO EJECUTIVO")
    y -= 1 * cm

    c.setFont("Helvetica", 9)
    fecha_generacion = datetime.now().strftime('%Y-%m-%d %H:%M')
    c.drawString(2 * cm, y, f"Generado: {fecha_generacion}")
    y -= 1.5 * cm

    # Cabecera tabla
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "Fecha")
    c.drawString(5 * cm, y, "Concepto")
    c.drawString(14 * cm, y, "Monto")
    y -= 0.7 * cm

    c.setFont("Helvetica", 9)

    # Detalle pagos
    for evento in eventos:
        linea_fecha = evento.fecha.strftime('%Y-%m-%d')
        linea_concepto = evento.pago.nombre[:45]
        linea_monto = f"${evento.monto:,.0f}"

        c.drawString(2 * cm, y, linea_fecha)
        c.drawString(5 * cm, y, linea_concepto)
        c.drawRightString(19 * cm, y, linea_monto)

        y -= 0.6 * cm

        if y < 2.5 * cm:
            c.showPage()
            y = height - 2 * cm

    # Total general
    y -= 1 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, f"TOTAL GENERAL: ${total:,.0f}")

    c.save()


# ============================
# PDF RESUMEN GERENCIAL
# ============================

def exportar_resumen_pdf(resumen, ruta):
    """
    Genera un PDF resumen ejecutivo financiero.
    """

    c = canvas.Canvas(ruta, pagesize=A4)
    width, height = A4

    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "RESUMEN FINANCIERO EJECUTIVO")
    y -= 1.5 * cm

    c.setFont("Helvetica", 10)

    items = [
        ('Desde', resumen['desde']),
        ('Hasta', resumen['hasta']),
        ('Total programado', f"${resumen['total_programado']:,.0f}"),
        ('Total pagado', f"${resumen['total_pagado']:,.0f}"),
        ('Total pendiente', f"${resumen['total_pendiente']:,.0f}"),
        ('Total vencido', f"${resumen['total_vencido']:,.0f}"),
        ('Cantidad registros', resumen['cantidad_registros'])
    ]

    for k, v in items:
        c.drawString(2 * cm, y, f"{k}: {v}")
        y -= 0.9 * cm

    c.save()
