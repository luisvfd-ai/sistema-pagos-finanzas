from django.db import migrations, models
import django.db.models.deletion


def seed_categorias_recurrentes(apps, schema_editor):
    CategoriaRecurrente = apps.get_model('pagos', 'CategoriaRecurrente')
    PagoProgramado = apps.get_model('pagos', 'PagoProgramado')

    defaults = [
        ('SUELDO', 'Sueldo'),
        ('ARRIENDO', 'Arriendo'),
        ('LUZ', 'Luz'),
        ('AGUA', 'Agua'),
        ('INTERNET', 'Internet'),
        ('GAS', 'Gas'),
        ('GASTOS_COMUNES', 'Gastos comunes'),
        ('SERVICIO', 'Servicio'),
        ('HONORARIO', 'Honorario'),
        ('OTRO', 'Otro'),
    ]

    created = {}
    for orden, (codigo, nombre) in enumerate(defaults, start=1):
        obj, _ = CategoriaRecurrente.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': nombre,
                'descripcion': '',
                'activa': True,
                'orden': orden,
                'legacy_key': codigo,
            }
        )
        created[codigo] = obj.id

    for pago in PagoProgramado.objects.exclude(categoria_recurrente='').iterator():
        codigo = (pago.categoria_recurrente or '').strip().upper().replace('-', '_').replace(' ', '_')
        categoria_id = created.get(codigo)
        if categoria_id and not getattr(pago, 'categoria_recurrente_ref_id', None):
            pago.categoria_recurrente_ref_id = categoria_id
            pago.save(update_fields=['categoria_recurrente_ref'])


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0012_pagoprogramado_recurrentes_etapa1'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoriaRecurrente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=120)),
                ('codigo', models.CharField(max_length=40, unique=True)),
                ('descripcion', models.TextField(blank=True)),
                ('activa', models.BooleanField(default=True)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('legacy_key', models.CharField(blank=True, default='', max_length=40)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Categoría recurrente',
                'verbose_name_plural': 'Categorías recurrentes',
                'ordering': ['orden', 'nombre', 'id'],
            },
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='categoria_recurrente_ref',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pagos_programados_categoria', to='pagos.categoriarecurrente', verbose_name='Categoría recurrente'),
        ),
        migrations.AlterField(
            model_name='pagoprogramado',
            name='categoria_recurrente',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='Código categoría recurrente'),
        ),
        migrations.RunPython(seed_categorias_recurrentes, migrations.RunPython.noop),
    ]
