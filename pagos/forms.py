
from decimal import Decimal
from django import forms
from django.db.models import Sum

from .models import PagoReal, PagoProgramado, UnidadNegocio, CategoriaRecurrente


class PagoProgramadoForm(forms.ModelForm):
    unidad_negocio = forms.ModelChoiceField(
        queryset=UnidadNegocio.objects.none(),
        required=False,
        empty_label='Otros / sin asignar',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    categoria_recurrente_ref = forms.ModelChoiceField(
        queryset=CategoriaRecurrente.objects.none(),
        required=False,
        empty_label='Selecciona una categoría',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = PagoProgramado
        fields = [
            'nombre',
            'modo_programacion',
            'tipo',
            'categoria_recurrente_ref',
            'monto',
            'fecha_inicio',
            'frecuencia',
            'dia_vencimiento',
            'indefinido',
            'fecha_fin',
            'metodo_proyeccion',
            'monto_proyeccion_manual',
            'total_cuotas',
            'cuotas_restantes',
            'descripcion',
            'activo',
        ]

        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'modo_programacion': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'categoria_recurrente_ref': forms.Select(attrs={'class': 'form-select'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'frecuencia': forms.Select(attrs={'class': 'form-select'}),
            'dia_vencimiento': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'indefinido': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'metodo_proyeccion': forms.Select(attrs={'class': 'form-select'}),
            'monto_proyeccion_manual': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_cuotas': forms.NumberInput(attrs={'class': 'form-control'}),
            'cuotas_restantes': forms.NumberInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            qs = UnidadNegocio.objects.filter(activa=True).order_by('orden', 'nombre', 'id')
            categorias_qs = CategoriaRecurrente.objects.filter(activa=True).order_by('orden', 'nombre', 'id')
            instancia = getattr(self, 'instance', None)
            if instancia and instancia.pk and instancia.unidad_negocio_ref_id:
                qs = UnidadNegocio.objects.filter(id=instancia.unidad_negocio_ref_id) | qs
                qs = qs.order_by('orden', 'nombre', 'id').distinct()
            if instancia and instancia.pk and getattr(instancia, 'categoria_recurrente_ref_id', None):
                categorias_qs = CategoriaRecurrente.objects.filter(id=instancia.categoria_recurrente_ref_id) | categorias_qs
                categorias_qs = categorias_qs.order_by('orden', 'nombre', 'id').distinct()
            self.fields['unidad_negocio'].queryset = qs
            self.fields['categoria_recurrente_ref'].queryset = categorias_qs
        except Exception:
            self.fields['unidad_negocio'].queryset = UnidadNegocio.objects.none()
            self.fields['categoria_recurrente_ref'].queryset = CategoriaRecurrente.objects.none()

        instancia = getattr(self, 'instance', None)
        if instancia and instancia.pk:
            if instancia.unidad_negocio_ref_id:
                self.fields['unidad_negocio'].initial = instancia.unidad_negocio_ref
            elif instancia.unidad_negocio:
                try:
                    self.fields['unidad_negocio'].initial = UnidadNegocio.objects.filter(
                        codigo=instancia.unidad_negocio
                    ).first()
                except Exception:
                    pass

            if getattr(instancia, 'categoria_recurrente_ref_id', None):
                self.fields['categoria_recurrente_ref'].initial = instancia.categoria_recurrente_ref
            elif getattr(instancia, 'categoria_recurrente', None):
                try:
                    self.fields['categoria_recurrente_ref'].initial = CategoriaRecurrente.objects.filter(
                        codigo=instancia.categoria_recurrente
                    ).first()
                except Exception:
                    pass

        # Dejamos estos campos opcionales a nivel de formulario y validamos según modo.
        for nombre in (
            'tipo',
            'categoria_recurrente_ref',
            'frecuencia',
            'dia_vencimiento',
            'fecha_fin',
            'metodo_proyeccion',
            'monto_proyeccion_manual',
            'total_cuotas',
            'cuotas_restantes',
        ):
            if nombre in self.fields:
                self.fields[nombre].required = False

    def clean(self):
        cleaned_data = super().clean()

        monto = cleaned_data.get('monto')
        total_cuotas = cleaned_data.get('total_cuotas')
        cuotas_restantes = cleaned_data.get('cuotas_restantes')
        modo_programacion = str(cleaned_data.get('modo_programacion') or 'CUOTAS').upper().strip()

        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        dia_vencimiento = cleaned_data.get('dia_vencimiento')

        categoria_recurrente_ref = cleaned_data.get('categoria_recurrente_ref')
        metodo_proyeccion = cleaned_data.get('metodo_proyeccion') or 'FIJO'
        monto_proyeccion_manual = cleaned_data.get('monto_proyeccion_manual')
        indefinido = bool(cleaned_data.get('indefinido'))

        if monto is not None and monto < 0:
            self.add_error('monto', 'El monto no puede ser negativo.')

        if modo_programacion == 'CUOTAS':
            if total_cuotas in (None, ''):
                self.add_error('total_cuotas', 'Debes indicar el total de cuotas.')
            elif total_cuotas <= 0:
                self.add_error('total_cuotas', 'El total de cuotas debe ser mayor que 0.')

            if cuotas_restantes in (None, ''):
                self.add_error('cuotas_restantes', 'Debes indicar las cuotas restantes.')
            elif cuotas_restantes < 0:
                self.add_error('cuotas_restantes', 'Las cuotas restantes no pueden ser negativas.')

            if (
                total_cuotas not in (None, '') and
                cuotas_restantes not in (None, '') and
                cuotas_restantes > total_cuotas
            ):
                self.add_error(
                    'cuotas_restantes',
                    'Las cuotas restantes no pueden ser mayores que el total de cuotas.'
                )

        elif modo_programacion == 'UNICO':
            cleaned_data['tipo'] = 'unico'
            cleaned_data['frecuencia'] = 'unico'
            cleaned_data['total_cuotas'] = 1
            cleaned_data['cuotas_restantes'] = 1
            cleaned_data['categoria_recurrente_ref'] = None
            cleaned_data['categoria_recurrente'] = ''
            cleaned_data['indefinido'] = False
            cleaned_data['fecha_fin'] = None
            cleaned_data['dia_vencimiento'] = None
            cleaned_data['metodo_proyeccion'] = 'FIJO'
            cleaned_data['monto_proyeccion_manual'] = None

        elif modo_programacion == 'RECURRENTE':
            cleaned_data['tipo'] = 'fijo'
            cleaned_data['frecuencia'] = 'mensual'
            cleaned_data['total_cuotas'] = 1
            cleaned_data['cuotas_restantes'] = 1

            if not categoria_recurrente_ref:
                self.add_error('categoria_recurrente_ref', 'Debes seleccionar una categoría recurrente.')
            else:
                cleaned_data['categoria_recurrente_ref'] = categoria_recurrente_ref
                cleaned_data['categoria_recurrente'] = categoria_recurrente_ref.codigo

            if fecha_inicio and not dia_vencimiento:
                cleaned_data['dia_vencimiento'] = fecha_inicio.day
            elif dia_vencimiento is None:
                self.add_error('dia_vencimiento', 'Debes indicar el día de vencimiento mensual.')
            else:
                try:
                    dia_vencimiento_int = int(dia_vencimiento)
                    if not (1 <= dia_vencimiento_int <= 31):
                        raise ValueError
                    cleaned_data['dia_vencimiento'] = dia_vencimiento_int
                except Exception:
                    self.add_error('dia_vencimiento', 'El día de vencimiento debe estar entre 1 y 31.')

            if indefinido:
                cleaned_data['fecha_fin'] = None
            else:
                if fecha_fin and fecha_inicio and fecha_fin < fecha_inicio:
                    self.add_error('fecha_fin', 'La fecha fin no puede ser anterior a la fecha inicio.')

            if metodo_proyeccion == 'MANUAL':
                if monto_proyeccion_manual in (None, ''):
                    self.add_error('monto_proyeccion_manual', 'Debes indicar el monto manual de proyección.')
                elif monto_proyeccion_manual < 0:
                    self.add_error('monto_proyeccion_manual', 'El monto manual de proyección no puede ser negativo.')
            else:
                cleaned_data['monto_proyeccion_manual'] = None

        else:
            self.add_error('modo_programacion', 'Modo de programación inválido.')

        return cleaned_data

    def save(self, commit=True):
        unidad = self.cleaned_data.get('unidad_negocio')
        categoria_ref = self.cleaned_data.get('categoria_recurrente_ref')
        instance = super().save(commit=False)
        instance.unidad_negocio_ref = unidad
        instance.unidad_negocio = unidad.codigo if unidad else (instance.unidad_negocio or 'otros')

        modo_programacion = str(self.cleaned_data.get('modo_programacion') or 'CUOTAS').upper().strip()
        instance.modo_programacion = modo_programacion

        if modo_programacion == 'UNICO':
            instance.tipo = 'unico'
            instance.frecuencia = 'unico'
            instance.total_cuotas = 1
            instance.cuotas_restantes = 1
            instance.categoria_recurrente_ref = None
            instance.categoria_recurrente = ''
            instance.indefinido = False
            instance.fecha_fin = None
            instance.dia_vencimiento = None
            instance.metodo_proyeccion = 'FIJO'
            instance.monto_proyeccion_manual = None

        elif modo_programacion == 'RECURRENTE':
            instance.tipo = 'fijo'
            instance.frecuencia = 'mensual'
            instance.total_cuotas = 1
            instance.cuotas_restantes = 1
            instance.categoria_recurrente_ref = categoria_ref
            instance.categoria_recurrente = categoria_ref.codigo if categoria_ref else (self.cleaned_data.get('categoria_recurrente') or 'OTRO')
            instance.dia_vencimiento = self.cleaned_data.get('dia_vencimiento') or (instance.fecha_inicio.day if instance.fecha_inicio else 1)
            instance.metodo_proyeccion = self.cleaned_data.get('metodo_proyeccion') or 'FIJO'

            if self.cleaned_data.get('indefinido'):
                instance.indefinido = True
                instance.fecha_fin = None
            else:
                instance.indefinido = False
                instance.fecha_fin = self.cleaned_data.get('fecha_fin')

            if instance.metodo_proyeccion == 'MANUAL':
                instance.monto_proyeccion_manual = self.cleaned_data.get('monto_proyeccion_manual')
            else:
                instance.monto_proyeccion_manual = None

        else:
            instance.categoria_recurrente_ref = None
            if not instance.total_cuotas:
                instance.total_cuotas = 1
            if instance.cuotas_restantes is None:
                instance.cuotas_restantes = instance.total_cuotas

            instance.categoria_recurrente_ref = None
            instance.categoria_recurrente = ''
            instance.indefinido = False
            instance.fecha_fin = None
            instance.dia_vencimiento = None
            instance.metodo_proyeccion = 'FIJO'
            instance.monto_proyeccion_manual = None

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class UnidadNegocioForm(forms.ModelForm):
    class Meta:
        model = UnidadNegocio
        fields = ['nombre', 'codigo', 'descripcion', 'orden', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_codigo(self):
        codigo = (self.cleaned_data.get('codigo') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if not codigo:
            nombre = (self.cleaned_data.get('nombre') or '').strip().lower().replace('-', '_').replace(' ', '_')
            codigo = nombre or 'otros'
        return codigo[:40]


class CategoriaRecurrenteForm(forms.ModelForm):
    class Meta:
        model = CategoriaRecurrente
        fields = ['nombre', 'codigo', 'descripcion', 'orden', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_codigo(self):
        codigo = (self.cleaned_data.get('codigo') or '').strip().upper().replace('-', '_').replace(' ', '_')
        if not codigo:
            nombre = (self.cleaned_data.get('nombre') or '').strip().upper().replace('-', '_').replace(' ', '_')
            codigo = nombre or 'OTRO'
        return codigo[:40]


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

        if monto is None:
            return monto

        if monto <= 0:
            raise forms.ValidationError('El monto debe ser mayor que cero.')

        if pago:
            saldo_real = pago.saldo_pendiente_real(
                excluir_pago_real_id=self.instance.pk if self.instance and self.instance.pk else None
            )

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
