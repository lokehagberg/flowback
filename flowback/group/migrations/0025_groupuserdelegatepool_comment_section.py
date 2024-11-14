# Generated by Django 4.2.7 on 2024-04-08 12:59

from django.db import migrations, models
import django.db.models.deletion

import flowback.comment.models
import flowback.comment.services


class Migration(migrations.Migration):

    dependencies = [
        ('comment', '0005_comment_attachments'),
        ('group', '0024_alter_groupuser_chat_participant'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupuserdelegatepool',
            name='comment_section',
            field=models.ForeignKey(default=flowback.comment.models.comment_section_create_model_default, on_delete=django.db.models.deletion.CASCADE, to='comment.commentsection'),
        ),
    ]
