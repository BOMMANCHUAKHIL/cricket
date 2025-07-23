# admin.py
from django.contrib import admin
from .models import Member

class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'user')
    list_filter = ('user',)  # Show user filter in the sidebar (for admin only)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Superuser sees all, normal users see only their own data
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def get_list_filter(self, request):
        # Only show the filter if user is admin
        if request.user.is_superuser:
            return self.list_filter
        return ()  # No filter for normal users

admin.site.register(Member, MemberAdmin)
from django.contrib import admin
from .models import Member, Team, Match, BallEvent


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'created_at', 'generation_id')
    list_filter = ('user', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('members',)
    readonly_fields = ('created_at', 'updated_at', 'generation_id')
    date_hierarchy = 'created_at'

    # Optional: Uncomment if you previously added filtering here
    # def get_queryset(self, request):
    #     qs = super().get_queryset(request)
    #     return qs.filter(user=request.user)  # ❌ Remove or comment this if exists

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'team1', 'team2', 'total_overs', 'start_time', 'completed', 'user')
    list_filter = ('completed', 'start_time')
    search_fields = ('team1__name', 'team2__name')


@admin.register(BallEvent)
class BallEventAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'match', 'innings', 'over', 'ball_in_over',
        'batsman', 'bowler', 'runs', 'is_catch', 'is_wicket', 'out_of_box', 'fielder'
    )
    list_filter = ('innings', 'is_catch', 'is_wicket', 'out_of_box')
    search_fields = ('batsman', 'bowler', 'fielder')
    ordering = ('match', 'innings', 'over', 'ball_in_over')
