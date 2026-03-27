from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_merge_20260326_2317'),
    ]

    operations = [
        migrations.AddField(
            model_name='building',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='building_photos/'),
        ),
        migrations.AddField(
            model_name='floor',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='floor_photos/'),
        ),
        migrations.AddField(
            model_name='room',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='room_photos/'),
        ),
    ]
