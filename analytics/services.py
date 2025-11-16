"""
Analytics service functions for tracking events and retrieving metrics.
"""
from datetime import datetime, timedelta
from django.db.models import Count,Sum
from django.utils import timezone
from .models import Event, DailyMetric, MonthlyMetric, FeatureMetric
from django.db.models.functions import TruncDate

def track_event(org, user, event_name, properties=None, timestamp=None):
    """
    Track a user event.
    
    Args:
        org: Organization instance
        user: User instance 
        event_name: Name of the event 
        properties: Dictionary of event properties 
        timestamp: Event timestamp (defaults to current time)
    
    Returns:
        Event instance
    """
    if properties is None:
        properties = {}
    
    if timestamp is None:
        timestamp = timezone.now()
    
    event = Event.objects.create(
        organization=org,
        user=user,
        name=event_name,
        properties=properties,
        timestamp=timestamp,
    )
    
    return event


def get_dau(org, start_date, end_date):
    """
    Get Daily Active Users (DAU) for a date range.
    
    Args:
        org: Organization instance
        start_date: Start date (datetime.date or datetime)
        end_date: End date (datetime.date or datetime)
    
    Returns:
        List of dictionaries with 'date' and 'dau' keys
    """
    # Convert datetime to date if necessary
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    # Get actual DAU data from events
    dau_data = (
        Event.objects.filter(
            organization=org,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date,
            user__isnull=False,
        )
        .annotate(date=TruncDate("timestamp"))  # extract date
        .values("date")
        .annotate(dau=Count("user", distinct=True))
        .order_by("date")
    )
    
    # Create a dictionary for quick lookup
    dau_dict = {item['date']: item['dau'] for item in dau_data}
    
    # Generate results for all dates in range, filling in 0 for missing dates
    results = []
    current_date = start_date
    while current_date <= end_date:
        results.append({
            'date': current_date,
            'dau': dau_dict.get(current_date, 0)
        })
        current_date += timedelta(days=1)
    
    return results


def get_wau(org, start_date, end_date):
    """
    Get Weekly Active Users (WAU) for a date range.
    Returns the number of unique users active in each 7-day period.
    
    Args:
        org: Organization instance
        start_date: Start date (datetime.date or datetime)
        end_date: End date (datetime.date or datetime)
    
    Returns:
        List of dictionaries with 'week_start', 'week_end', and 'wau' keys
    """
    
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    results = []
    current_date = start_date
    
    while current_date <= end_date:
        week_end = min(current_date + timedelta(days=6), end_date)
        
        # Count distinct users in this week
        wau = Event.objects.filter(
            organization=org,
            timestamp__date__gte=current_date,
            timestamp__date__lte=week_end,
            user__isnull=False
        ).values('user').distinct().count()
        
        results.append({
            'week_start': current_date,
            'week_end': week_end,
            'wau': wau
        })
        
        current_date = week_end + timedelta(days=1)
    
    return results


def get_mau(org, start_date, end_date):
    """
    Get Monthly Active Users (MAU) for a date range.
    Returns the count of unique users active within the specified date range.
    
    Args:
        org: Organization instance
        start_date: Start date (datetime.date or datetime)
        end_date: End date (datetime.date or datetime)
    
    Returns:
        Integer count of unique users
    """
    
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    results = []
    # Count distinct users who had events in the date range
    mau = Event.objects.filter(
        organization=org,
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date,
        user__isnull=False
    ).values('user').distinct().count()

    results.append({
        'month_start': start_date,
        'month_end': end_date,
        'mau': mau
    })

    return results

def get_revenue_timeseries(org, start_date, end_date):
    """
    Get revenue time series data for a date range.
    
    Args:
        org: Organization instance
        start_date: Start date (datetime.date or datetime)
        end_date: End date (datetime.date or datetime)
    
    Returns:
        List of dictionaries with 'date' and 'revenue_cents' keys
    """
    # Convert datetime to date if necessary
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    # Query DailyMetric table for revenue data
    metrics = DailyMetric.objects.filter(
        organization=org,
        date__gte=start_date,
        date__lte=end_date
    ).values('date', 'revenue_cents').order_by('date')
    
    # Convert to list
    results = list(metrics)
    
    # If no metrics exist -> return empty list
    # In a production system/env, we might want to aggregate from events
    # or subscription data instead
    return results


def get_top_events(org, limit=10, start_date=None, end_date=None):
    """
    Get the top events by occurrence count.
    
    Args:
        org: Organization instance
        limit: Maximum number of events to return (default: 10)
        start_date: Optional start date to filter events (datetime.date or datetime)
        end_date: Optional end date to filter events (datetime.date or datetime)
    
    Returns:
        List of dictionaries with 'event_name' and 'count' keys
    """
    query = Event.objects.filter(organization=org)
    
    # Apply date filters if provided
    if start_date:
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        query = query.filter(timestamp__date__gte=start_date)
    
    if end_date:
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        query = query.filter(timestamp__date__lte=end_date)
    
    # Group by event name and count occurrences
    top_events = query.values('name').annotate(
        count=Count('id')
    ).order_by('-count')[:limit]
    
    # Convert to list of dicts with clearer naming
    results = []
    for item in top_events:
        results.append({
            'event_name': item['name'],
            'count': item['count']
        })
    
    return results


def get_top_features(org, start_date=None, end_date=None, limit=10):
    """
    Get the most used features within a date range for an organization.

    Args:
        org: Organization instance
        start_date: Optional start date (datetime.date)
        end_date: Optional end date (datetime.date)
        limit: Max number of features to return (default: 10)

    Returns:
        List of dictionaries: [{ 'feature_name': str, 'total_usage': int, 'unique_users': int }]
    """
    query = FeatureMetric.objects.filter(organization=org)

    if start_date:
        query = query.filter(date__gte=start_date)
    if end_date:
        query = query.filter(date__lte=end_date)

    # Aggregate usage count and unique users across the range
    data = (
        query.values("feature_name")
        .annotate(
            total_usage=Sum("usage_count"),
            total_unique_users=Sum("unique_users")
        )
        .order_by("-total_usage")[:limit]
    )

    return list(data)


def get_least_used_features(org, start_date=None, end_date=None, limit=10):
    """
    Get the least used (underused) features within a date range for an organization.

    Args:
        org: Organization instance
        start_date: Optional start date (datetime.date)
        end_date: Optional end date (datetime.date)
        limit: Max number of features to return (default: 10)

    Returns:
        List of dictionaries: [{ 'feature_name': str, 'total_usage': int, 'unique_users': int }]
    """
    query = FeatureMetric.objects.filter(organization=org)

    if start_date:
        query = query.filter(date__gte=start_date)
    if end_date:
        query = query.filter(date__lte=end_date)

    data = (
        query.values("feature_name")
        .annotate(
            total_usage=Sum("usage_count"),
            total_unique_users=Sum("unique_users")
        )
        .order_by("total_usage")[:limit]  
    )

    return list(data)