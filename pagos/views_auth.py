from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, Permission, User
from django.shortcuts import render, redirect, get_object_or_404

from .forms_auth import UsuarioCrearForm, UsuarioEditarForm


ROLE_GROUPS = {
    'administrador': 'Administrador',
    'operador': 'Operador',
    'visualizador': 'Visualizador',
}


def _ensure_roles_and_permissions():
    grupos = {}
    for _, nombre in ROLE_GROUPS.items():
        grupo, _ = Group.objects.get_or_create(name=nombre)
        grupos[nombre] = grupo

    permisos_admin = [
        # Pagos
        'view_pagoprogramado', 'add_pagoprogramado', 'change_pagoprogramado',
        'view_pagoreal', 'add_pagoreal', 'change_pagoreal',
        'view_eventopago',
        # Cartolas / conciliación
        'view_movimientobancario', 'add_movimientobancario', 'change_movimientobancario',
        # Importaciones
        'view_importacionpago', 'add_importacionpago', 'change_importacionpago', 'delete_importacionpago',
        'view_importacionpagodetalle',
        # Usuarios
        'view_user', 'add_user', 'change_user',
    ]

    permisos_operador = [
        # Pagos
        'view_pagoprogramado',
        'view_pagoreal', 'add_pagoreal', 'change_pagoreal',
        'view_eventopago',
        # Cartolas / conciliación
        'view_movimientobancario', 'add_movimientobancario', 'change_movimientobancario',
        # Importaciones
        'view_importacionpago', 'add_importacionpago',
        'view_importacionpagodetalle',
    ]

    permisos_visualizador = [
    'view_pagoprogramado',
    'view_pagoreal',
    'view_eventopago',
    'view_importacionpago',
    'view_importacionpagodetalle',
]

    def asignar_permisos(grupo, codenames):
        perms = Permission.objects.filter(codename__in=codenames)
        grupo.permissions.set(perms)

    asignar_permisos(grupos['Administrador'], permisos_admin)
    asignar_permisos(grupos['Operador'], permisos_operador)
    asignar_permisos(grupos['Visualizador'], permisos_visualizador)


def _rol_usuario(user):
    if user.is_superuser:
        return 'Superadmin'

    nombres = list(user.groups.values_list('name', flat=True))
    if 'Administrador' in nombres:
        return 'Administrador'
    if 'Operador' in nombres:
        return 'Operador'
    if 'Visualizador' in nombres:
        return 'Visualizador'
    return 'Sin rol'


def _rol_key_desde_usuario(user):
    if user.groups.filter(name='Administrador').exists():
        return 'administrador'
    if user.groups.filter(name='Operador').exists():
        return 'operador'
    if user.groups.filter(name='Visualizador').exists():
        return 'visualizador'
    return 'visualizador'


def _asignar_rol(user, rol_key):
    user.groups.clear()
    group_name = ROLE_GROUPS.get(rol_key)
    if group_name:
        group = Group.objects.get(name=group_name)
        user.groups.add(group)


def home_redirect(request):
    _ensure_roles_and_permissions()

    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.has_perm('pagos.view_pagoprogramado'):
        return redirect('dashboard_financiero')

    if request.user.has_perm('auth.view_user'):
        return redirect('usuarios_lista')

    messages.error(request, 'Tu usuario no tiene permisos asignados para entrar al sistema.')
    return redirect('logout_view')


def login_view(request):
    _ensure_roles_and_permissions()

    if request.user.is_authenticated:
        return redirect('home_redirect')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bienvenido, {user.username}.')
            return redirect('home_redirect')
        messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')


@login_required
@permission_required('auth.view_user', raise_exception=True)
def usuarios_lista(request):
    _ensure_roles_and_permissions()

    usuarios = User.objects.all().prefetch_related('groups').order_by('username')

    data = []
    for u in usuarios:
        data.append({
            'obj': u,
            'rol': _rol_usuario(u),
        })

    return render(request, 'pagos/usuarios_lista.html', {
        'usuarios': data,
    })


@login_required
@permission_required('auth.add_user', raise_exception=True)
def usuario_crear(request):
    _ensure_roles_and_permissions()

    if request.method == 'POST':
        form = UsuarioCrearForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email')
            user.first_name = form.cleaned_data.get('first_name')
            user.last_name = form.cleaned_data.get('last_name')
            user.is_active = form.cleaned_data.get('is_active', True)
            user.is_staff = False
            user.save()

            rol = form.cleaned_data.get('rol')
            _asignar_rol(user, rol)

            messages.success(request, f'Usuario {user.username} creado correctamente.')
            return redirect('usuarios_lista')

        messages.error(request, 'Revisa el formulario de creación de usuario.')
    else:
        form = UsuarioCrearForm()

    return render(request, 'pagos/usuario_form.html', {
        'form': form,
        'titulo': 'Nuevo usuario',
        'modo_edicion': False,
        'usuario_obj': None,
        'es_superadmin': False,
    })


@login_required
@permission_required('auth.change_user', raise_exception=True)
def usuario_editar(request, pk):
    _ensure_roles_and_permissions()

    usuario = get_object_or_404(User, pk=pk)

    if usuario.is_superuser:
        messages.warning(request, 'Los superusuarios deben gestionarse desde Django Admin.')
        return redirect('usuarios_lista')

    rol_inicial = _rol_key_desde_usuario(usuario)

    if request.method == 'POST':
        form = UsuarioEditarForm(request.POST, instance=usuario, rol_inicial=rol_inicial)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email')
            user.first_name = form.cleaned_data.get('first_name')
            user.last_name = form.cleaned_data.get('last_name')
            user.is_active = form.cleaned_data.get('is_active', True)
            user.save()

            rol = form.cleaned_data.get('rol')
            _asignar_rol(user, rol)

            messages.success(request, f'Usuario {user.username} actualizado correctamente.')
            return redirect('usuarios_lista')

        messages.error(request, 'Revisa el formulario de edición.')
    else:
        form = UsuarioEditarForm(instance=usuario, rol_inicial=rol_inicial)

    return render(request, 'pagos/usuario_form.html', {
        'form': form,
        'titulo': f'Editar usuario: {usuario.username}',
        'modo_edicion': True,
        'usuario_obj': usuario,
        'es_superadmin': False,
    })