# Generated by Django 4.2.7 on 2024-06-11 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0030_alter_group_direct_join_alter_group_public'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupuserdelegatepool',
            name='blockchain_id',
            field=models.PositiveIntegerField(blank=True, default=None, null=True),
        ),
    ]
