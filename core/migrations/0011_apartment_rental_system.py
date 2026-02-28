# Generated migration - Convert from hotel booking to apartment rental

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_alter_booking_options_alter_room_options_and_more'),
    ]

    operations = [
        # Create Apartment model (replaces Room)
        migrations.CreateModel(
            name='Apartment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unit_number', models.CharField(max_length=10, unique=True)),
                ('apartment_type', models.CharField(choices=[('studio', 'Studio'), ('one_bedroom', '1 Bedroom'), ('two_bedroom', '2 Bedroom'), ('three_bedroom', '3 Bedroom'), ('four_bedroom', '4 Bedroom')], max_length=20)),
                ('monthly_rent', models.DecimalField(decimal_places=2, max_digits=10)),
                ('max_occupants', models.IntegerField()),
                ('description', models.TextField()),
                ('is_available', models.BooleanField(default=True)),
                ('amenities', models.TextField(help_text='Comma-separated amenities')),
                ('image_url', models.URLField(blank=True, null=True)),
            ],
        ),
        # Create Lease model (replaces Booking)
        migrations.CreateModel(
            name='Lease',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('move_in_date', models.DateField()),
                ('move_out_date', models.DateField(blank=True, help_text='Leave blank for ongoing lease', null=True)),
                ('num_occupants', models.IntegerField()),
                ('total_lease_price', models.DecimalField(decimal_places=2, help_text='Total cost for the lease period', max_digits=10)),
                ('monthly_rent', models.DecimalField(blank=True, decimal_places=2, help_text='Monthly rent amount', max_digits=10, null=True)),
                ('lease_type', models.CharField(choices=[('fixed_term', 'Fixed Term Lease'), ('month_to_month', 'Month-to-Month Lease')], default='fixed_term', help_text='Type of lease', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending Approval'), ('active', 'Active Lease'), ('cancelled', 'Cancelled'), ('completed', 'Lease Ended')], default='pending', max_length=20)),
                ('special_requests', models.TextField(blank=True, null=True)),
                ('rent_due_day', models.IntegerField(blank=True, help_text='Day of month when rent is due (1-31)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('apartment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.apartment')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        # Create RentPayment model (replaces Payment)
        migrations.CreateModel(
            name='RentPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('gcash', 'GCash'), ('card', 'Credit/Debit Card'), ('bank', 'Bank Transfer')], max_length=20)),
                ('payment_status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('partial', 'Partially Paid'), ('refunded', 'Refunded')], default='pending', max_length=20)),
                ('transaction_id', models.CharField(blank=True, max_length=100, null=True)),
                ('payment_date', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('lease', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='core.lease')),
            ],
        ),
        # Create RentDueDate model (replaces DuePayment)
        migrations.CreateModel(
            name='RentDueDate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('due_date', models.DateField()),
                ('amount_due', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_paid', models.BooleanField(default=False)),
                ('is_recurring_monthly', models.BooleanField(default=True, help_text='If True, this rent recurs monthly')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lease', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='due_dates', to='core.lease')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rent_dues', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['due_date'],
            },
        ),
        # Update Maintenance model references
        migrations.AddField(
            model_name='maintenance',
            name='apartment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='maintenance_requests', to='core.apartment'),
        ),
        migrations.AddField(
            model_name='maintenance',
            name='lease',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.lease'),
        ),
        migrations.AlterField(
            model_name='maintenance',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_requests', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='maintenance',
            name='room',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='maintenance_requests_old', to='core.room'),
        ),
        # Update Event model references
        migrations.AddField(
            model_name='event',
            name='apartment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.apartment'),
        ),
    ]
