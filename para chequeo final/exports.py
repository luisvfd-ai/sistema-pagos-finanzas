import pandas as pd
from django.utils import timezone


# ============================
# EXPORTACIÓN EXCEL PROFESIONAL
# ============================

def exportar_a_excel(eventos, ruta):
    """
    Exporta una lista de eventos de pago a un archivo Excel profesional,
    con totales automáticos y formato limpio para gerencia.
    """

    data = []

    for evento in eventos:
        data.append({
            'Fecha': evento.fecha.strftime('%Y-%m-%d'),
            'Concepto': evento.pago.nombre,
            'Tipo': evento.pago.tipo,
            'Monto': float(evento.monto),
            'Estado': evento.estado
        })

    if not data:
        data.append({
            'Fecha': '',
            'Concepto': 'Sin registros',
            'Tipo': '',
            'Monto': 0,
            'Estado': ''
        })

    df = pd.DataFrame(data)

    # Fila de totales automáticos
    df.loc['TOTAL'] = ['', '', '', df['Monto'].sum(), '']

    df.to_excel(ruta, index=False)


# ============================
# EXPORTACIÓN RESUMEN FINANCIERO
# ============================

def exportar_resumen_excel(resumen, ruta):
    """
    Exporta un resumen financiero a Excel.
    """
    data = [
        ['Desde', resumen['desde']],
        ['Hasta', resumen['hasta']],
        ['Total programado', resumen['total_programado']],
        ['Total pagado', resumen['total_pagado']],
        ['Total pendiente', resumen['total_pendiente']],
        ['Total vencido', resumen['total_vencido']],
        ['Cantidad registros', resumen['cantidad_registros']]
    ]

    df = pd.DataFrame(data, columns=['Concepto', 'Valor'])
    df.to_excel(ruta, index=False)
