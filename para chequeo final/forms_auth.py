from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

ROL_CHOICES = [
    ('administrador', 'Administrador'),
    ('operador', 'Operador'),
    ('visualizador', 'Visualizador'),
]


class UsuarioCrearForm(UserCreationForm):
    first_name = forms.CharField(required=False, label="Nombre")
    last_name = forms.CharField(required=False, label="Apellido")
    email = forms.EmailField(required=False, label="Correo")
    rol = forms.ChoiceField(choices=ROL_CHOICES, label="Rol")
    is_active = forms.BooleanField(required=False, initial=True, label="Activo")

    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'rol',
            'is_active',
            'password1',
            'password2',
        )


class UsuarioEditarForm(forms.ModelForm):
    rol = forms.ChoiceField(choices=ROL_CHOICES, label="Rol")
    is_active = forms.BooleanField(required=False, label="Activo")

    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'rol',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        rol_inicial = kwargs.pop('rol_inicial', None)
        super().__init__(*args, **kwargs)
        if rol_inicial:
            self.fields['rol'].initial = rol_inicial