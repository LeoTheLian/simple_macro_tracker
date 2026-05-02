"""
Add nullable user FK to LogEntry and DailyGoal.
Replace DailyGoal unique on effective_date with per-user constraint.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0001_initial'),
    ]

    operations = [
        # 1. Add nullable user to LogEntry
        migrations.AddField(
            model_name='logentry',
            name='user',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='log_entries',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 2. Add nullable user to DailyGoal
        migrations.AddField(
            model_name='dailygoal',
            name='user',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='daily_goals',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 3. Remove old unique on effective_date
        migrations.AlterField(
            model_name='dailygoal',
            name='effective_date',
            field=models.DateField(default=django.utils.timezone.now),
        ),
    ]
