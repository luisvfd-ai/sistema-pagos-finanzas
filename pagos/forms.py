from decimal import Decimal
from django import forms
from django.db.models import Sum

from .models import PagoReal, PagoProgramado


class PagoProgramadoForm(forms.ModelForm):

    class Meta:
        model = PagoProgramado
        fields = [
            'nombre',
            'tipo',
            'monto',
            'fecha_inicio',
            'frecuencia',
            'total_cuotas',
            'cuotas_restantes',
            'descripcion',
            'activo',
        ]

        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'frecuencia': forms.Select(attrs={'class': 'form-select'}),
            'total_cuotas': forms.NumberInput(attrs={'class': 'form-control'}),
            'cuotas_restantes': forms.NumberInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        monto = cleaned_data.get('monto')
        total_cuotas = cleaned_data.get('total_cuotas')
        cuotas_restantes = cleaned_data.get('cuotas_restantes')

        if monto is not None and monto < 0:
            self.add_error('monto', 'El monto no puede ser negativo.')

        if total_cuotas is not None and total_cuotas <= 0:
            self.add_error('total_cuotas', 'El total de cuotas debe ser mayor que 0.')

        if cuotas_restantes is not None and cuotas_restantes < 0:
            self.add_error('cuotas_restantes', 'Las cuotas restantes no pueden ser negativas.')

        if (
            total_cuotas is not None and
            cuotas_restantes is not None and
            cuotas_restantes > total_cuotas
        ):
            self.add_error(
                'cuotas_restantes',
                'Las cuotas restantes no pueden ser mayores que el total de cuotas.'
            )

        return cleaned_data


class PagoRealForm(forms.ModelForm):

    class Meta:
        model = PagoReal
        fields = [
            'pago',
            'fecha_pago',
            'monto',
            'metodo_pago',
            'observacion',
        ]

        widgets = {
            'pago': forms.Select(attrs={'class': 'form-select'}),
            'fecha_pago': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_monto(self):
        monto = self.cleaned_data['monto']
        pago = self.cleaned_data.get('pago')

        if pago:
            saldo_real = pago.saldo_pendiente_real(excluir_pago_real_id=self.instance.pk if self.instance and self.instance.pk else None)

            if saldo_real < 0:
                saldo_real = Decimal('0.00')

            if monto > saldo_real:
                raise forms.ValidationError(
                    f"El monto no puede superar el saldo real pendiente disponible para este registro (${saldo_real:,.0f})"
                )

        return monto


# ==================================================
# IMPORT CARTOLAS (CSV/XLSX)
# ==================================================

class CartolaImportForm(forms.Form):
    archivo = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )

    cuenta = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Cuenta Corriente 1234"})
    )

    banco = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: BancoEstado / Santander"})
    )

    col_fecha = forms.CharField(
        required=False,
        initial="fecha",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre columna fecha (ej: Fecha)"})
    )
    col_descripcion = forms.CharField(
        required=False,
        initial="descripcion",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre columna descripción (ej: Descripción)"})
    )
    col_monto = forms.CharField(
        required=False,
        initial="monto",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre columna monto (ej: Monto)"})
    )
    col_referencia = forms.CharField(
        required=False,
        initial="referencia",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional (ej: Referencia)"})
    )
    col_tipo = forms.CharField(
        required=False,
        initial="tipo",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional (cargo/abono)"})
    )

    separador_csv = forms.ChoiceField(
        required=False,
        choices=((',', 'Coma ,'), (';', 'Punto y coma ;'), ('\t', 'Tab')),
        initial=';',
        widget=forms.Select(attrs={"class": "form-select"})
    )


# ==================================================
# AUTO-CONCILIACIÓN
# ==================================================

class AutoConciliacionForm(forms.Form):
    score_minimo = forms.IntegerField(
        required=False,
        initial=85,
        min_value=45,
        max_value=100,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": "45",
            "max": "100"
        })
    )

    limite = forms.IntegerField(
        required=False,
        initial=200,
        min_value=1,
        max_value=1000,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": "1",
            "max": "1000"
        })
    )

    desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    solo_pendientes = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )


# ==================================================
# IMPORTACIÓN MASIVA DE DEUDAS / PAGOS DESDE EXCEL
# ==================================================

class PagosImportExcelForm(forms.Form):
    archivo = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )

    hoja = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Opcional. Ej: Hoja1"
        })
    )

    crear_pagos_reales = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
