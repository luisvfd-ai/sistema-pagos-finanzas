from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0010_empresaconfig'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='pagoprogramado',
            name='anulado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='anulado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagos_programados_anulados', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='pagoprogramado',
            name='motivo_anulacion',
            field=models.TextField(blank=True, default=''),
        ),
    ]
