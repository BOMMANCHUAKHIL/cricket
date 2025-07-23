from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
urlpatterns = [
    path('generate/', views.generate_teams, name='generate_teams'),
    path('teams/', views.team_list, name='team_list'),
    path('teamss/', views.team_lists, name='team_lists'),  # Changed from 'teamss'
    path('team/<int:team_id>/', views.team_detail, name='team_detail'),
    path('', views.add_members_in_pair, name='add_member'),
    path('coin-flip/', views.coin_flip, name='coin_flip'),
    path('add-member/', views.add_member_to_team, name='add_member_to_team'),
    path('reorder-members/', views.reorder_members, name='reorder_members'),
    path('members/edit/<int:member_id>/', views.edit_member, name='edit_member'),
    path('download-teams/', views.download_teams, name='download_teams'),
    path('member/delete/<int:entity_id>/', views.delete_member, name='delete_member'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('start/', views.start_match, name='start_match'),                      # Select two teams to start a match
    path('match/<int:match_id>/', views.match_detail, name='match_detail'),
    path('record/<int:match_id>/', views.record_ball, name='record_ball'),     # Record ball for a specific match
    path('scorecard/<int:match_id>/', views.scorecard, name='scorecard'),       # View scorecard for a specific match
    path('leaderboard/<int:match_id>/', views.leaderboard, name='leaderboard'), # Leaderboard for that match
    path('team/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('match/<int:match_id>/swap-innings/', views.swap_innings, name='swap_innings'),
    path('match/<int:match_id>/delete/', views.delete_match, name='delete_match'),
    path('ajax/get_team_members/<int:team_id>/', views.get_team_members, name='get_team_members'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard_view'),
    # path('update-captains/', update_captains, name='update_captains'),
    path('tournament/', views.start_tournament, name='tournament'),
    path('tournament/<int:tournament_id>/', views.tournament_detail, name='tournament_detail'),
    path('delete-tournament/<int:tournament_id>/', views.delete_tournament, name='delete_tournament'),
    path('team/delete/<int:team_id>/', views.delete_team, name='delete_team'),  # Add this
    path('teams/delete-multiple/', views.delete_multiple_teams, name='delete_multiple_teams'),
    path('tournament/<int:tournament_id>/leaderboard/', views.tournament_leaderboard, name='tournament_leaderboard'),
]