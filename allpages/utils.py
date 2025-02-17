# allpages/utils.py
from datetime import date, timedelta

def get_thursday_to_wednesday_range(ref_date):
    """Calculates the Thursday to Wednesday range for a given date."""
    ref_date_weekday = ref_date.weekday()
    days_since_thursday = (ref_date_weekday - 3) % 7
    start_date = ref_date - timedelta(days=days_since_thursday)
    end_date = start_date + timedelta(days=6)
    return start_date, end_date