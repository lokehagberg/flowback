# Generated by Django 4.2.7 on 2024-03-04 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0021_group_chat_alter_group_kanban_alter_group_schedule'),
    ]

    operations = [
        migrations.AlterField(
            model_name='group',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
    ]
