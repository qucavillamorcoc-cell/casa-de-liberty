from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_remove_apartmentphoto_photo_url_apartmentphoto_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='apartmentphoto',
            name='photo_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
