# analytics/tasks.py
import datetime
from celery import shared_task
from django.db.models import Count, Sum
from django.utils import timezone
from organizations.models import Organization
from .models import Event, DailyMetric, MonthlyMetric, FeatureMetric


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def aggregate_daily_metrics(self):
    """
    Aggregate daily metrics for all organizations.
    Runs once per day (scheduled via Celery Beat).

    args:
        self: The task instance

    Returns:
        dict: Status of the task
    """
    try:
        today = timezone.now().date()
        yesterday = today - datetime.timedelta(days=1)

        for org in Organization.objects.all():
            dau = (
                Event.objects.filter(
                    organization=org,
                    timestamp__date=yesterday
                ).values("user").distinct().count()
            )            
            new_users = (
                Event.objects.filter(
                    organization=org,
                    timestamp__date=yesterday
                )
                .values("user")
                .annotate(first_event=Min("timestamp"))
                .filter(first_event__date=yesterday)
                .count()
            )

            revenue_cents = (
                DailyMetric.objects.filter(
                    organization=org, date=yesterday
                ).aggregate(total=Sum("revenue_cents"))["total"] or 0
            )

            DailyMetric.objects.update_or_create(
                organization=org,
                date=yesterday,
                defaults={
                    "dau": dau,
                    "new_users": new_users,
                    "revenue_cents": revenue_cents,
                },
            )


        return {
            'status': 'success',
            'message': f'Daily metrics aggregation completed for {yesterday}.'
        }

    except Exception as exc:
        # Retry the task if it fails
        raise self.retry(exc=exc)   


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def aggregate_monthly_metrics(self):
    """
    Aggregate monthly metrics for all organizations.
    Runs once per month via Celery Beat.

    args: 
        self: The task instance

    Returns:
        dict: Status of the task
    """
    try:
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month_end = first_day - datetime.timedelta(days=1)
        month = last_month_end.month
        year = last_month_end.year

        for org in Organization.objects.all():
            mau = (
                Event.objects.filter(
                    organization=org,
                    timestamp__year=year,
                    timestamp__month=month,
                ).values("user").distinct().count()
            )

            mrr_cents = (
                DailyMetric.objects.filter(
                    organization=org,
                    date__year=year,
                    date__month=month,
                ).aggregate(total=Sum("revenue_cents"))["total"] or 0
            )

            churn_rate = None  # placeholder, if you track subscriptions

            MonthlyMetric.objects.update_or_create(
                organization=org,
                year=year,
                month=month,
                defaults={
                    "mau": mau,
                    "mrr_cents": mrr_cents,
                    "churn_rate": churn_rate,
                },
            )

            return {
                'status': 'success',
                'message': f'Monthly metrics aggregation completed for {year}-{month:02d}.'
            }

    except Exception as exc:
        # Retry the task if it fails
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def aggregate_feature_metrics(self):
    """
    Optional task: aggregates daily feature usage from Event logs.

    args:
        self: The task instance

    Returns:
        dict: Status of the task
    """
    try:
        yesterday = timezone.now().date() - datetime.timedelta(days=1)

        for org in Organization.objects.all():
            feature_usage = (
                Event.objects.filter(
                    organization=org,
                    timestamp__date=yesterday,
                    properties__has_key="feature_name"
                )
                .values("properties__feature_name")
                .annotate(usage_count=Count("id"), unique_users=Count("user", distinct=True))
            )

            for item in feature_usage:
                FeatureMetric.objects.update_or_create(
                    organization=org,
                    feature_name=item["properties__feature_name"],
                    date=yesterday,
                    defaults={
                        "usage_count": item["usage_count"],
                        "unique_users": item["unique_users"],
                        "last_used_at": timezone.now(),
                    },
                )

        return {
            'status': 'success',
            'message': f'Feature metrics aggregation completed for {yesterday}.'
        }

    except Exception as exc:
        # Retry the task if it fails
        raise self.retry(exc=exc)