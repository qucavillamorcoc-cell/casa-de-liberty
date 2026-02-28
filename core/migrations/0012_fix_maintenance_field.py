# Fix Maintenance model field naming

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_apartment_rental_system'),
    ]

    operations = [
        # Remove the old 'user' field and ensure 'tenant' exists
        migrations.RemoveField(
            model_name='maintenance',
            name='user',
        ),
        migrations.AddField(
            model_name='maintenance',
            name='tenant',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_requests', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
