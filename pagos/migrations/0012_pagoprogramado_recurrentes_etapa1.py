from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0011_pagoprogramado_anulacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='pagoprogramado',
            name='modo_programacion',
            field=models.CharField(choices=[('CUOTAS', 'En cuotas'), ('RECURRENTE', 'Recurrente mensual'), ('UNICO', 'Único')], default='CUOTAS', max_length=20),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='categoria_recurrente',
            field=models.CharField(blank=True, choices=[('SUELDO', 'Sueldo'), ('ARRIENDO', 'Arriendo'), ('LUZ', 'Luz'), ('AGUA', 'Agua'), ('INTERNET', 'Internet'), ('GAS', 'Gas'), ('GASTOS_COMUNES', 'Gastos comunes'), ('SERVICIO', 'Servicio'), ('HONORARIO', 'Honorario'), ('OTRO', 'Otro')], default='', max_length=30),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='indefinido',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='fecha_fin',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='dia_vencimiento',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='metodo_proyeccion',
            field=models.CharField(choices=[('FIJO', 'Monto fijo'), ('MANUAL', 'Monto manual'), ('PROMEDIO_3M', 'Promedio últimos 3 meses'), ('PROMEDIO_6M', 'Promedio últimos 6 meses')], default='FIJO', max_length=20),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='monto_proyeccion_manual',
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
    ]
