from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('dau', models.IntegerField(default=0)),
                ('new_users', models.IntegerField(default=0)),
                ('revenue_cents', models.BigIntegerField(default=0)),
                ('organization', models.ForeignKey(help_text='Organization this metric belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='daily_metrics', to='organizations.organization')),
            ],
        ),
        migrations.CreateModel(
            name='MonthlyMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField()),
                ('month', models.IntegerField()),
                ('mau', models.IntegerField(default=0)),
                ('mrr_cents', models.BigIntegerField(default=0)),
                ('churn_rate', models.FloatField(blank=True, null=True)),
                ('organization', models.ForeignKey(help_text='Organization this metric belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='monthly_metrics', to='organizations.organization')),
            ],
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier for the event', primary_key=True, serialize=False)),
                ('name', models.CharField(db_index=True, max_length=200)),
                ('properties', models.JSONField(blank=True, default=dict)),
                ('timestamp', models.DateTimeField(db_index=True)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('organization', models.ForeignKey(help_text='Organization this event belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='events', to='organizations.organization')),
                ('user', models.ForeignKey(blank=True, help_text='User who triggered this event (optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='monthlymetric',
            index=models.Index(fields=['organization', 'year', 'month'], name='analytics_m_organiz_4bc3a3_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='monthlymetric',
            unique_together={('organization', 'year', 'month')},
        ),
        migrations.AddIndex(
            model_name='dailymetric',
            index=models.Index(fields=['organization', 'date'], name='analytics_d_organiz_2f71a0_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='dailymetric',
            unique_together={('organization', 'date')},
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['organization', 'timestamp'], name='analytics_e_organiz_ae6d52_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['organization', 'name', 'timestamp'], name='analytics_e_organiz_eb8e95_idx'),
        ),
    ]

