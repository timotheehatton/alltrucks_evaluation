"""Widen KnowledgeBaseCase CharField sizes.

The initial migration sized several CharFields too small for the historical
CSV (vin=50 was rejected on Postgres because real VINs go up to 59 chars).
This widens fields to ~2× the observed max so the data populate (0024)
succeeds and there's headroom for legacy edge cases.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('mail_parser', '0022_knowledgebasecase'),
    ]

    operations = [
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='engine',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='registration_date',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='vin',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='mileage',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='axle_configuration',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='abs_configuration',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='installed_system',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AlterField(
            model_name='knowledgebasecase',
            name='system',
            field=models.CharField(blank=True, db_index=True, default='', max_length=200),
        ),
    ]
