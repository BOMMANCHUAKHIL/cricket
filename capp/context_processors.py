# capp/context_processors.py
from .models import Match, Tournament
from django.utils import timezone
from datetime import timedelta

def live_matches_context(request):
    """Add live matches and tournaments to all templates"""
    
    # Get live matches (active in last 30 minutes)
    recent_threshold = timezone.now() - timedelta(minutes=30)
    live_matches = Match.objects.filter(
        is_live=True,
        last_activity__gte=recent_threshold
    ).exclude(completed=True).select_related('team1', 'team2')[:5]
    
    # Get live tournaments
    live_tournaments = Tournament.objects.filter(
        is_live=True,
        last_activity__gte=recent_threshold
    ).exclude(completed=True)[:5]
    
    return {
        'live_matches': live_matches,
        'live_tournaments': live_tournaments,
    }