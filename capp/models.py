from django.db import models
from django.contrib.auth.models import User
# Add to your models.py

class Member(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    position = models.IntegerField(default=0)  # For ordering
    is_captain = models.BooleanField(default=False)
    is_selected = models.BooleanField(default=False)
    last_selected = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.position + 1}: {self.name}{' (C)' if self.is_captain else ''}"

    class Meta:
        ordering = ['-last_selected','position']
        # unique_together = ['user']  # Prevent same position for same user
        # constraints = [
        #     models.UniqueConstraint(
        #         fields=['user', 'name'],
        #         name='unique_user_member_name'
        #     ),
        #     models.UniqueConstraint(
        #         fields=['user', 'position'],
        #         name='unique_user_position'
        #     )
        # ]
import uuid
class Team(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(Member, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # when team was created
    updated_at = models.DateTimeField(auto_now=True)      # when team was last updated
    generation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    @property
    def captain(self):
        return self.members.filter(is_captain=True).first()
    def __str__(self):
        return f"{self.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    class Meta:
        ordering = ['-created_at']  # Default ordering by newest first

class Tournament(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    teams = models.ManyToManyField(Team)
    total_overs = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    single_batting = models.BooleanField(
        default=False,
        verbose_name="Single Batting Mode",
        help_text="When enabled, innings ends only when no batters remain"
    )
    completed = models.BooleanField(default=False)
    # ADD THESE NEW FIELDS FOR LIVE STATUS
    is_live = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    def get_matches(self):
        return Match.objects.filter(tournament=self).order_by('-created_at')

    def get_winner(self):
        if not self.completed:
            return None
        # Implement your tournament winner logic here
        # This could be based on points, wins, etc.
        return None
    @property
    def status(self):
        if self.completed:
            return "Completed"
        elif self.is_live:
            return "Live"
        else:
            return "Upcoming"

    class Meta:
        ordering = ['-last_activity', '-created_at']


class Match(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    team1 = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='team1_matches')
    team2 = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='team2_matches')
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, null=True, blank=True)
    total_overs = models.PositiveIntegerField()  # e.g. 5 overs match
    start_time = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    current_innings = models.IntegerField(default=1)
    completed = models.BooleanField(default=False)
    team1_score = models.PositiveIntegerField(default=0)
    team2_score = models.PositiveIntegerField(default=0)
    winner = models.ForeignKey('Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_won')
    single_batting = models.BooleanField(
        default=False,
        verbose_name="Single Batting Mode",
        help_text="When enabled, innings ends only when no batters remain"
    )
    # ADD THESE NEW FIELDS FOR LIVE STATUS
    is_live = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.team1.name} vs {self.team2.name} ({self.start_time.strftime('%Y-%m-%d %H:%M')}) - {self.total_overs} Overs"
    def total_balls(self):
        return self.total_overs * 6

    def current_ball_count(self):
        return self.balls.count()

    def is_completed(self):
        return self.current_ball_count() >= self.total_balls()
    @property
    def status(self):
        if self.completed:
            return "Completed"
        elif self.is_live:
            return "Live"
        else:
            return "Upcoming"

    class Meta:
        ordering = ['-last_activity', '-created_at']


class BallEvent(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='balls')
    over = models.IntegerField()
    ball_in_over = models.IntegerField()
    batsman = models.CharField(max_length=100)
    batsman_id = models.PositiveIntegerField(null=True, blank=True)
    bowler_id = models.PositiveIntegerField(null=True, blank=True)
    fielder_id = models.PositiveIntegerField(null=True, blank=True)
    bowler = models.CharField(max_length=100)
    runs = models.IntegerField(default=0)
    is_catch = models.BooleanField(default=False)
    is_wicket = models.BooleanField(default=False)
    out_of_box = models.BooleanField(default=False)
    is_runout = models.BooleanField(default=False)
    fielder = models.CharField(max_length=100, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    INNINGS_CHOICES = [(1, 'First'), (2, 'Second')]
    innings = models.PositiveSmallIntegerField(choices=INNINGS_CHOICES, default=1)
    def is_dismissal(self):
        return any([self.is_catch, self.is_wicket, self.out_of_box])
    def __str__(self):
        events = []
        if self.is_catch:
            events.append(f"Catch by {self.fielder}")
        if self.is_wicket:
            events.append(f"Wicket by {self.fielder}")
        if self.out_of_box:
            events.append(f"out_of_box near {self.fielder}")
        if self.runs == 0 and not events:
            events.append("Dot ball")

        event_str = " | ".join(events)
        return f"Over {self.over}.{self.ball_in_over}: {self.bowler} to {self.batsman} - {self.runs}r {event_str}"

    class Meta:
        ordering = ['match', 'over', 'ball_in_over']
        indexes = [
            models.Index(fields=['batsman']),
            models.Index(fields=['bowler']),
            models.Index(fields=['fielder']),
            models.Index(fields=['is_wicket']),
            models.Index(fields=['is_catch']),
        ]

# models.py
from django.db import models

class TournamentStats(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='stats')
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    matches_played = models.PositiveIntegerField(default=0)
    matches_won = models.PositiveIntegerField(default=0)
    matches_lost = models.PositiveIntegerField(default=0)
    matches_drawn = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=0)
    net_run_rate = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tournament', 'team')
        ordering = ['-points', '-net_run_rate']

    def __str__(self):
        return f"{self.team.name} - {self.points} pts"

