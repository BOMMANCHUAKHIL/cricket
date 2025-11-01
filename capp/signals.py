from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q, F  # Add these imports
from .models import Match, TournamentStats

@receiver(post_save, sender=Match)
def update_tournament_stats(sender, instance, created, **kwargs):
    if instance.completed and instance.tournament:
        # Update stats for both teams
        for team in [instance.team1, instance.team2]:
            stats, created = TournamentStats.objects.get_or_create(
                tournament=instance.tournament,
                team=team
            )
            stats.matches_played = Match.objects.filter(
                Q(team1=team) | Q(team2=team),
                tournament=instance.tournament,
                completed=True
            ).count()
            
            stats.matches_won = Match.objects.filter(
                Q(team1=team, team1_score__gt=F('team2_score')) |
                Q(team2=team, team2_score__gt=F('team1_score')),
                tournament=instance.tournament,
                completed=True
            ).count()
            
            stats.matches_lost = Match.objects.filter(
                Q(team1=team, team1_score__lt=F('team2_score')) |
                Q(team2=team, team2_score__lt=F('team1_score')),
                tournament=instance.tournament,
                completed=True
            ).count()
            
            stats.matches_drawn = stats.matches_played - stats.matches_won - stats.matches_lost
            stats.points = stats.matches_won * 2 + stats.matches_drawn
            stats.save()