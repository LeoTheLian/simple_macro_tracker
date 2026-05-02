"""
Backfill existing LogEntry and DailyGoal rows with a default 'legacy' user,
then make the user FK non-nullable and add the per-user uniqueness constraint.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_user(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    LogEntry = apps.get_model('tracker', 'LogEntry')
    DailyGoal = apps.get_model('tracker', 'DailyGoal')

    # Create or fetch the legacy owner
    user, _ = User.objects.get_or_create(
        username='legacy-owner',
        defaults={'is_active': True, 'is_staff': False},
    )

    LogEntry.objects.filter(user__isnull=True).update(user=user)
    DailyGoal.objects.filter(user__isnull=True).update(user=user)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0002_add_user_to_logentry_dailygoal'),
    ]

    operations = [
        # 1. Backfill data
        migrations.RunPython(backfill_user, migrations.RunPython.noop),

        # 2. Make user non-nullable on LogEntry
        migrations.AlterField(
            model_name='logentry',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='log_entries',
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # 3. Make user non-nullable on DailyGoal
        migrations.AlterField(
            model_name='dailygoal',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='daily_goals',
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # 4. Add the per-user uniqueness constraint on DailyGoal
        migrations.AddConstraint(
            model_name='dailygoal',
            constraint=models.UniqueConstraint(
                fields=['user', 'effective_date'],
                name='unique_user_goal_date',
            ),
        ),
    ]
