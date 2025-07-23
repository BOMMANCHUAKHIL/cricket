
# views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Team, Member
from .forms import TeamSplitForm
import random
import uuid
from .models import Tournament
import itertools
@login_required
def generate_teams(request):
    if request.method == 'POST':
        form = TeamSplitForm(request.POST, user=request.user)
        if form.is_valid():
            # Get all members ordered by position
            selected_members = form.cleaned_data['members']
            members = Member.objects.filter(
                user=request.user,
                id__in=selected_members.values_list('id', flat=True)
            ).order_by('position')

            # Separate captains and regular members
            captains = list(members.filter(is_captain=True))
            regular_members = list(members.filter(is_captain=False))
            total_members = len(captains) + len(regular_members)

            # Validate inputs
            if total_members == 0:
                form.add_error('members', 'Please select at least one member')
                return render(request, 'generate_teams.html', {'form': form})

            # Set num_teams equal to number of captains
            num_teams = len(captains) if captains else 1
            if num_teams == 0:
                # If no captains, create one team or promote top member as captain
                num_teams = 1
                if regular_members:
                    captains = [regular_members[0]]
                    regular_members = regular_members[1:]

            if total_members < num_teams:
                form.add_error('members', f'Not enough members ({total_members}) for {num_teams} teams')
                return render(request, 'generate_teams.html', {'form': form})

            generation_id = uuid.uuid4()
            teams = []

            # PHASE 1: Create teams with captains
            for i in range(num_teams):
                captain = captains[i] if i < len(captains) else None
                team_name = f"{captain.name.upper()}'S TEAM" if captain else f"Team {i+1}"
                team = Team.objects.create(
                    name=team_name,
                    user=request.user,
                    generation_id=generation_id
                )
                if captain:
                    team.members.add(captain)
                teams.append(team)

            # PHASE 2: Prepare all players (captains + regular)
            all_players = captains + regular_members
            remaining_players = [p for p in all_players if p not in [t.members.first() for t in teams if t.members.exists()]]

            # PHASE 3: Position-based distribution with snake draft
            remaining_players.sort(key=lambda x: x.position)

            # Distribute players in position order using snake draft
            for i, player in enumerate(remaining_players):
                # Snake draft pattern
                if (i // num_teams) % 2 == 1:  # Reverse direction
                    team_index = num_teams - 1 - (i % num_teams)
                else:  # Forward direction
                    team_index = i % num_teams

                teams[team_index].members.add(player)

            # Ensure equal counts
            team_counts = [t.members.count() for t in teams]
            min_count = min(team_counts)
            max_count = max(team_counts)

            # Balance teams if needed (max 1 difference)
            if max_count - min_count > 1:
                for team in teams:
                    while team.members.count() > min_count + 1:
                        # Get members sorted by position (highest first)
                        members = list(team.members.all().order_by('-position'))
                        # Find first non-captain to move
                        for member in members:
                            if not member.is_captain:
                                team.members.remove(member)
                                # Add to smallest team
                                smallest_team = min(teams, key=lambda t: t.members.count())
                                smallest_team.members.add(member)
                                break

            request.session['latest_generation_id'] = str(generation_id)
            return redirect('team_list')

    else:
        initial_members = request.session.get('selected_members', [])
        form = TeamSplitForm(user=request.user, initial={'members': initial_members})

    return render(request, 'generate_teams.html', {'form': form})

def coin_flip(request):
    # Get or initialize session counts
    heads_count = request.session.get('heads_count', 0)
    tails_count = request.session.get('tails_count', 0)

    # Flip the coin
    result = random.choice(['Heads', 'Tails'])

    # Update counts
    if result == 'Heads':
        heads_count += 1
    else:
        tails_count += 1

    # Save to session
    request.session['heads_count'] = heads_count
    request.session['tails_count'] = tails_count
    total_flips = heads_count + tails_count

    context = {
        'result': result,
        'coin_class': 'animate-coin' if request.GET.get('animate') else '',
        'final_rotation': 0 if result == 'Heads' else 180,
        'heads_count': heads_count,
        'tails_count': tails_count,
        'total_flips': total_flips
    }
    return render(request, 'coin_flip.html', context)

# teams/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Team
from django.utils import timezone

@login_required
def team_lists(request):
    # Debug: Print team count to console
    team_count = Team.objects.filter(user=request.user).count()
    print(f"Found {team_count} teams for user {request.user}")

    teams = Team.objects.filter(user=request.user).select_related('user').prefetch_related('members')

    # Debug: Print raw team data
    print("Teams queryset:", list(teams.values('id', 'name', 'generation_id', 'created_at')))

    generations = {}
    for team in teams:
        if team.generation_id not in generations:
            generations[team.generation_id] = {
                'teams': [],
                'created_at': team.created_at,
                'total_members': 0
            }
        generations[team.generation_id]['teams'].append(team)
        generations[team.generation_id]['total_members'] += team.members.count()

    # Debug: Print generation data
    print("Generations dict:", generations)

    generations_list = sorted(
        generations.items(),
        key=lambda item: item[1]['created_at'],
        reverse=True
    )

    context = {
        'generations': generations_list,
        'now': timezone.now(),
        'debug_team_count': team_count  # Pass to template
    }
    return render(request, 'team_lists.html', context)
from django.shortcuts import render
import uuid
from .models import Team, Member
from django.contrib.auth.decorators import login_required

def team_list(request):
    # Get the most recently generated teams
    if request.user.is_authenticated:
        # For authenticated users: show their latest generation
        generation_id_str = request.session.get('latest_generation_id')
        if generation_id_str:
            try:
                generation_id = uuid.UUID(generation_id_str)
                latest_teams = Team.objects.filter(
                    user=request.user,
                    generation_id=generation_id
                ).prefetch_related('members').order_by('-created_at')
            except (ValueError, AttributeError):
                latest_teams = Team.objects.none()
        else:
            latest_teams = Team.objects.none()
    else:
        # For anonymous users: show the most recently generated teams from any user
        # First get the latest generation ID
        latest_generation = Team.objects.latest('created_at').generation_id
        # Then get all teams with that generation ID
        latest_teams = Team.objects.filter(
            generation_id=latest_generation
        ).prefetch_related('members').order_by('-created_at')

    # Prepare context data
    context = {
        'teams': latest_teams,
        'user': request.user,
        'total_members': 0,
        'available_members': [],
        'debug': False
    }

    # Only calculate member data if user is authenticated
    if request.user.is_authenticated and latest_teams.exists():
        all_members = Member.objects.filter(user=request.user)
        context['total_members'] = all_members.count()

        team_member_ids = set()
        for team in latest_teams:
            team_member_ids.update(team.members.values_list('id', flat=True))

        context['available_members'] = all_members.exclude(id__in=team_member_ids)
        context['debug'] = True

    return render(request, 'team_list.html', context)


# views.py
from django.shortcuts import render, get_object_or_404
from .models import Team

def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    members = team.members.all().order_by('position')
    matches_as_team1 = team.team1_matches.all()
    matches_as_team2 = team.team2_matches.all()
    all_matches = matches_as_team1 | matches_as_team2

    context = {
        'team': team,
        'members': members,
        'matches': all_matches,
        'captain': team.captain,
    }
    return render(request, 'team_detail.html', context)  # Ensure correct template path
@login_required
def team_management(request):
    """Protected view for team management actions"""
    # Your existing team management logic
    pass


# capp/views.py
@login_required
def add_member_to_team(request):
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        team_id = request.POST.get('team_id')

        try:
            member = Member.objects.get(id=member_id, user=request.user)
            team = Team.objects.get(id=team_id, user=request.user)

            team.members.add(member)
            messages.success(request, f"Added {member.name} to {team.name}")
        except (Member.DoesNotExist, Team.DoesNotExist):
            messages.error(request, "Invalid member or team selection")

    return redirect('team_list')



from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Max
from django.contrib import messages
from .models import Member
from .forms import MemberPairForm
@login_required
def add_members_in_pair(request):
    # Get members for the logged-in user, with captains first
    members = Member.objects.filter(user=request.user).order_by('-is_captain', 'position')

    if request.method == 'POST':
        if 'update_captains' in request.POST:
            # Handle captain updates from the member list
            Member.objects.filter(user=request.user).update(is_captain=False)
            for member in members:
                if f'captain_{member.id}' in request.POST:
                    member.is_captain = True
                    member.save()
            messages.success(request, "Captain selections updated!")
            return redirect('add_member')

        # Handle adding new members (your existing code)
        form = MemberPairForm(request.POST)
        if form.is_valid():
            name1 = form.cleaned_data['name1']
            name2 = form.cleaned_data['name2']
            last_position = members.aggregate(max_pos=Max('position'))['max_pos'] or -1

            Member.objects.create(
                user=request.user,
                name=name1,
                position=last_position + 1
            )
            Member.objects.create(
                user=request.user,
                name=name2,
                position=last_position + 2
            )
            messages.success(request, "Members added successfully!")
            return redirect('add_member')
    else:
        form = MemberPairForm()

    return render(request, 'add_member.html', {
        'form': form,
        'members': members
    })
from django.shortcuts import render, get_object_or_404, redirect
from .models import Member
from .forms import MemberForm

def edit_member(request, member_id):
    member = get_object_or_404(Member, id=member_id)

    if request.method == 'POST':
        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            return redirect('add_member')  # or another view
    else:
        form = MemberForm(instance=member)

    return render(request, 'edit_member.html', {'form': form})





from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect
import json
from .models import Member

@login_required
@require_http_methods(["GET", "POST"])
def reorder_members(request):
    members = Member.objects.filter(user=request.user).order_by('position')

    bg_classes = ['bg-set-1', 'bg-set-2', 'bg-set-3']
    for index, member in enumerate(members):
        member.bg_class = bg_classes[index % 3]  # Rotate through the 3 colors

    if request.method == "POST":
        order_data = request.POST.get('order_data')
        if order_data:
            order_list = json.loads(order_data)
            user_members = Member.objects.filter(user=request.user)
            user_member_ids = set(user_members.values_list('id', flat=True))

            # Temporary offset to avoid unique constraint conflicts
            temp_offset = 1000
            for member_id in order_list:
                if int(member_id) in user_member_ids:
                    Member.objects.filter(id=member_id).update(position=temp_offset)
                    temp_offset += 1

            # Final position update
            for index, member_id in enumerate(order_list):
                if int(member_id) in user_member_ids:
                    Member.objects.filter(id=member_id).update(position=index)

        return redirect('reorder_members')

    # Refresh ordered members with bg_class assigned
    members = Member.objects.filter(user=request.user).order_by('position')
    for index, member in enumerate(members):
        member.bg_class = bg_classes[index % 3]

    return render(request, 'reorder.html', {'members': members})





# import csv
# from django.http import HttpResponse
# from .models import Team

# def download_teams(request):
#     teams = Team.objects.all()
#     team_members = [list(team.members.values_list('name', flat=True)) for team in teams]
#     max_length = max(len(members) for members in team_members) if team_members else 0

#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="teams.csv"'

#     writer = csv.writer(response)

#     # Header row: team names
#     writer.writerow([team.name for team in teams])

#     # Member rows
#     for i in range(max_length):
#         row = []
#         for members in team_members:
#             row.append(members[i] if i < len(members) else "")
#         writer.writerow(row)

#     return response
import csv
from django.http import HttpResponse
from django.utils import timezone
from .models import Team

def download_teams(request):
    # Get the most recently created team's generation ID
    latest_team = Team.objects.order_by('-created_at').first()

    if not latest_team:
        response = HttpResponse("No teams available", content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="no_teams.txt"'
        return response

    # Get all teams from the latest generation
    teams = Team.objects.filter(
        generation_id=latest_team.generation_id
    ).order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    filename = f"teams_{latest_team.generation_id}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Write headers
    writer.writerow(['Team Name', 'Created (IST)', 'Members'])

    # Write team data with localized times
    for team in teams:
        local_time = timezone.localtime(team.created_at)  # Automatically uses TIME_ZONE
        members = ", ".join([m.name for m in team.members.all()])
        writer.writerow([
            team.name,
            local_time.strftime('%b %d, %Y %H:%M'),  # Format: Jun 23, 2025 10:19
            members
        ])

    return response
from django.shortcuts import get_object_or_404, redirect
from .models import Member  # Ensure Member model is imported

@login_required
def delete_multiple_teams(request):
    if request.method == 'POST':
        team_ids = request.POST.getlist('team_ids')
        Team.objects.filter(id__in=team_ids, user=request.user).delete()
        messages.success(request, 'Selected teams deleted successfully!')
    return redirect('team_list')
@login_required
def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, user=request.user)
    if request.method == 'POST':
        team.delete()
        messages.success(request, 'Team deleted successfully!')
        return redirect('start_match')
    return redirect('start_match')

from .models import Match  # import Match model
@login_required
def delete_member(request, entity_id):
    entity_type = request.GET.get('type')

    if entity_type == 'team':
        team = get_object_or_404(Team, id=entity_id, user=request.user)
        team.delete()
        return redirect('start_match')  # You don't have an 'add_team', so this fits best.

    elif entity_type == 'member':
        member = get_object_or_404(Member, id=entity_id, user=request.user)
        member.delete()
        return redirect('add_member')  # You do have this URL

    elif entity_type == 'match':
        match = get_object_or_404(Match, id=entity_id, user=request.user)
        match.delete()
        return redirect('start_match')  # This takes the user to the match start page

    else:
        print("Invalid type:", entity_type)
        return redirect('generate_teams')  # Fallback

from capp.models import Member
from django.db.models import Count

duplicates = (
    Member.objects.values('position')
    .annotate(pos_count=Count('id'))
    .filter(pos_count__gt=1)
)

for dup in duplicates:
    print(f"Position {dup['position']} is used by {dup['pos_count']} members.")

duplicate_positions = [dup['position'] for dup in duplicates]

conflicting_members = Member.objects.filter(position__in=duplicate_positions).order_by('position')

for m in conflicting_members:
    print(f"{m.name} (Position: {m.position})")


from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import render, redirect

def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # auto-login after signup
            return redirect('add_member')  # redirect to any protected page
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Team, Member, Match, BallEvent

from django.shortcuts import render, redirect, get_object_or_404
from .models import Team, Match
from django.contrib.auth.decorators import login_required

@login_required
def start_match(request):
    user = request.user
    teams = Team.objects.filter(user=user)
    matches = Match.objects.filter(user=user).order_by('-created_at')

    # Get tournament from GET or POST
    tournament_id = request.GET.get('tournament') or request.POST.get('tournament')
    tournament = None
    if tournament_id:
        tournament = get_object_or_404(Tournament, id=tournament_id, user=user)

    if request.method == 'POST':
        team1_id = request.POST.get('team1')
        team2_id = request.POST.get('team2')
        total_overs = request.POST.get('total_overs')
        single_batting = 'single_batting' in request.POST

        if team1_id and team2_id and total_overs:
            team1 = get_object_or_404(Team, id=team1_id, user=user)
            team2 = get_object_or_404(Team, id=team2_id, user=user)

            match = Match.objects.create(
                user=user,
                team1=team1,
                team2=team2,
                tournament=tournament,  # Set tournament reference
                total_overs=int(total_overs),
                single_batting=single_batting
            )
            return redirect('record_ball', match_id=match.id)

    # Use tournament settings if available
    if tournament:
        total_overs = tournament.total_overs
        single_batting = tournament.single_batting
    else:
        total_overs = 5  # Default
        single_batting = False

    return render(request, 'start_match.html', {
        'teams': teams,
        'matches': matches,
        'total_overs': total_overs,
        'single_batting': single_batting,
        'tournament': tournament
    })


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from .models import Match, BallEvent, Team, Member
from django.utils.timezone import now
from django.contrib import messages
from .forms import BallEventForm


@login_required
def match_detail(request, match_id):
    match = get_object_or_404(Match, id=match_id, user=request.user)

    ball_events = BallEvent.objects.filter(match=match).order_by('over', 'ball_in_over')
    total_runs = sum(event.runs for event in ball_events)

    context = {
        'match': match,
        'ball_events': ball_events,
        'total_runs': total_runs,
        'is_completed': match.is_completed(),
    }
    return render(request, 'match_detail.html', context)
# def should_end_innings(team_members, match):
#     # In single batting mode, end only when there are 0 players left
#     # In normal mode, end when < 2 batters are left
#     min_batters = 0 if match.single_batting else 2
#     return team_members.count() < min_batters
# def should_end_innings(team_members, match):
#     # Safely get the boolean value, default to False if missing
#     is_single_mode = bool(getattr(match, 'single_batting', False))

#     # Single mode: end at 0 batters
#     if is_single_mode:
#         return team_members.count() == 0  # More explicit than <= 0

#     # Standard mode: end when < 2 batters
#     return team_members.count() < 2

# def should_end_innings(available_batters, match):
#     # Case 1: No batters left (all out)
#     if not available_batters.exists():
#         return True

#     # Case 2: Over limit reached (if applicable)
#     current_balls = BallEvent.objects.filter(
#         match=match,
#         innings=match.current_innings
#     ).count()
#     max_balls = match.total_overs * 6

#     if current_balls >= max_balls:
#         return True

#     return False
def should_end_innings(available_batters, match):
    """
    Determines if innings should end based on:
    1. Batting mode (single/normal)
    2. Available batters count
    3. Over limit
    """
    # Get batting mode (default False if not set)
    is_single_mode = getattr(match, 'single_batting', False)

    # Case 1: No batters left (all out) - applies to both modes
    if not available_batters.exists():
        return True

    # Case 2: Over limit reached (applies to both modes)
    current_balls = BallEvent.objects.filter(
        match=match,
        innings=match.current_innings
    ).count()
    max_balls = match.total_overs * 6

    if current_balls >= max_balls:
        return True

    # Case 3: Batter count check (differs by mode)
    if is_single_mode:
        # Single batting - only overs or all-out can end innings
        return False
    else:
        # Normal mode - end when < 2 batters remain
        return available_batters.count() < 2
@login_required
def record_ball(request, match_id):
    match = get_object_or_404(Match, id=match_id, user=request.user)
    request.session['current_match_id'] = match_id
    # Session keys
    session_key = f"freeze_teams_{match_id}"
    batting_key = f"batting_team_{match_id}"
    bowling_key = f"bowling_team_{match_id}"
    innings_started_key = f"second_innings_started_{match_id}"
    dismissed_players_key = f"dismissed_players_{match_id}"

    # Initialize session variables
    request.session.setdefault(batting_key, match.team1.id)
    request.session.setdefault(bowling_key, match.team2.id)
    request.session.setdefault(dismissed_players_key, [])

    # Get session values
    is_frozen = request.session.get(session_key, False)
    batting_team_id = request.session[batting_key]
    bowling_team_id = request.session[bowling_key]
    dismissed_players = request.session[dismissed_players_key]
    is_second_innings = request.session.get(innings_started_key, False)

    # Get Team objects
    batting_team = get_object_or_404(Team, id=batting_team_id, user=request.user)
    bowling_team = get_object_or_404(Team, id=bowling_team_id, user=request.user)

    # Get available players
    batting_team_members = batting_team.members.exclude(name__in=dismissed_players)
    bowling_team_members = bowling_team.members.all()

    # Get last event safely
    last_event = BallEvent.objects.filter(match=match).order_by('-timestamp').first()
    last_batsman_name = getattr(last_event, 'batsman', None) if last_event else None
    last_bowler_name = getattr(last_event, 'bowler', None) if last_event else None
    last_fielder_name = getattr(last_event, 'fielder', None) if last_event else None

    last_batsman_obj = Member.objects.filter(name=last_batsman_name, team=batting_team).first() if last_batsman_name else None
    last_bowler_obj = Member.objects.filter(name=last_bowler_name, team=bowling_team).first() if last_bowler_name else None
    last_fielder_obj = Member.objects.filter(name=last_fielder_name, team=bowling_team).first() if last_fielder_name else None
        # Calculate balls per innings
    all_events = BallEvent.objects.filter(match=match).order_by('over', 'ball_in_over')

    # Separate innings based on the innings field
    first_innings_events = [e for e in all_events if e.innings == 1]
    second_innings_events = [e for e in all_events if e.innings == 2]
    is_second_innings = len(second_innings_events) > 0 or match.current_innings == 2

    # Calculate balls per innings - MOVE THIS BEFORE POST HANDLING
    first_innings_balls = len(first_innings_events)
    second_innings_balls = len(second_innings_events) if is_second_innings else 0
    current_innings_balls = second_innings_balls if is_second_innings else first_innings_balls

    def calculate_innings_stats(events, dismissed_count):
        runs = sum(e.runs for e in events)
        balls = len(events)
        wickets = sum(1 for e in events if e.is_dismissal())
        overs = f"{balls//6}.{balls%6}"
        return {
            'runs': runs,
            'wickets': wickets,
            'balls': balls,
            'overs': overs,
            'score': f"{runs}/{wickets} in {overs} overs"
        }
    first_stats = calculate_innings_stats(first_innings_events, 0)  # Don't use session dismissed count
    second_stats = calculate_innings_stats(second_innings_events, 0) if is_second_innings else None

    # POST request
    if request.method == "POST":
        if "swap_teams" in request.POST and not is_second_innings:
            # if should_end_innings(batting_team_members, match):
            #     request.session[batting_key] = bowling_team_id
            #     request.session[bowling_key] = batting_team_id
            #     request.session[innings_started_key] = True
            #     request.session[dismissed_players_key] = []
            #     match.current_innings = 2
            #     match.save()
            #     return redirect('record_ball', match_id=match.id)
            if should_end_innings(batting_team_members, match):
                request.session[batting_key] = bowling_team_id
                request.session[bowling_key] = batting_team_id

                # Reset dismissed players for the new innings
                request.session[dismissed_players_key] = []

                # Mark second innings as started
                request.session[innings_started_key] = True

                # Update match state
                match.current_innings = 2
                match.save()
                messages.success(
                    request,
                    f"Innings swapped! Now {bowling_team.name} is batting and {batting_team.name} is bowling",
                    extra_tags="innings"
                )

                all_events = BallEvent.objects.filter(match=match).order_by('over', 'ball_in_over')
                first_innings_events = [e for e in all_events if e.innings == 1]
                second_innings_events = [e for e in all_events if e.innings == 2]
                bowling_team = get_object_or_404(Team, id=batting_team_id)  # Now the NEW bowling team
                bowling_team_members = bowling_team.members.all()

                # Redirect to refresh the page with updated data
                return redirect('record_ball', match_id=match.id)
            else:
                # Optionally, you can add a message here to inform the user
                messages.warning(request, "Innings cannot be swapped yet.")
        if "toggle_freeze" in request.POST:
            request.session[session_key] = not is_frozen
            return redirect('record_ball', match_id=match.id)

        if not is_frozen:
            new_batting_id = request.POST.get('batting_team')
            new_bowling_id = request.POST.get('bowling_team')
            if new_batting_id and Team.objects.filter(id=new_batting_id, user=request.user).exists():
                request.session[batting_key] = int(new_batting_id)
                batting_team = Team.objects.get(id=new_batting_id, user=request.user)
                batting_team_members = batting_team.members.exclude(name__in=dismissed_players)
            if new_bowling_id and Team.objects.filter(id=new_bowling_id, user=request.user).exists():
                request.session[bowling_key] = int(new_bowling_id)
                bowling_team = Team.objects.get(id=new_bowling_id, user=request.user)
                bowling_team_members = bowling_team.members.all()

        form = BallEventForm(
            request.POST,
            batting_team_members=batting_team_members,
            bowling_team_members=bowling_team_members,
            last_batsman_id=last_batsman_obj.id if last_batsman_obj else None,
            last_bowler_id=last_bowler_obj.id if last_bowler_obj else None,
        )


        if form.is_valid():
            ball = form.save(commit=False)
            ball.match = match
            total_balls = BallEvent.objects.filter(match=match).count()
            ball.over = total_balls // 6
            ball.ball_in_over = (total_balls % 6) + 1
            ball.innings = match.current_innings

            batsman = Member.objects.get(id=form.cleaned_data['batsman'])
            bowler = Member.objects.get(id=form.cleaned_data['bowler'])

            ball.batsman = batsman.name
            ball.bowler = bowler.name
            current_innings_balls = BallEvent.objects.filter(
                match=match,
                innings=match.current_innings
            ).count()


            # When over completes (6 balls)
            if (current_innings_balls+1) % 6 == 0 and current_innings_balls > 0:
                over_number = (current_innings_balls + 1) // 6
                inning_label = "Second" if is_second_innings else "First"
                current_bowler = last_event.bowler if last_event else "the bowler"  # Get current bowler name
                messages.info(request,
                    f"{inning_label} innings over {over_number} completed!.please Change the ({current_bowler}) ",extra_tags="over"
                )
            if not is_second_innings and should_end_innings(batting_team_members, match):
                messages.warning(request,
                    f"First innings completed! Final score: {innings.first.score}. "
                    f"Now {bowling_team.name} will bat and {batting_team.name} will bowl.")
            # When match completes
            # In your record_ball view, modify the match completion logic:
            # if is_second_innings and first_stats and second_stats and not match.completed:
            #     try:
            #         first_innings_team = bowling_team  # since batting and bowling were swapped
            #         second_innings_team = batting_team

            #         # Ensure we have valid scores
            #         if first_stats and second_stats:
            #             match.team1_score = first_stats.get('runs', 0) if match.team1 == first_innings_team else second_stats.get('runs', 0)
            #             match.team2_score = second_stats.get('runs', 0) if match.team1 == first_innings_team else first_stats.get('runs', 0)

            #             # Only proceed if scores are not None
            #             if match.team1_score is not None and match.team2_score is not None:
            #                 # Rest of your winner determination logic
            #                 match.save()
            #     except Exception as e:
            #         print(f"Error determining winner: {str(e)}")
            #         # Handle error appropriately

            if is_second_innings and second_stats and first_stats and not match.completed:
                # 1. Check if target reached (must be strictly greater than)
                target_reached = second_stats['runs'] > first_stats['runs']

                # 2. Check if innings should end
                is_single_mode = getattr(match, 'single_batting', False)
                available_batters = batting_team_members.count()
                innings_ended = (available_batters == 0) if is_single_mode else (available_batters < 2)

                # 3. Check if overs completed
                overs_completed = current_innings_balls >= match.total_overs * 6

                # 4. Determine if match should complete
                if target_reached or innings_ended or overs_completed:
                    # Calculate wickets remaining
                    total_players = batting_team.members.count()
                    wickets_remaining = total_players - len(dismissed_players) - 1  # -1 for current batter

                    # Set scores
                    match.team1_score = first_stats['runs'] if match.current_innings == 2 else second_stats['runs']
                    match.team2_score = second_stats['runs'] if match.current_innings == 2 else first_stats['runs']

                    # Determine winner
                    if target_reached:
                        match.winner = batting_team
                        winner_message = f"{batting_team.name} won by {wickets_remaining} wickets!"
                    elif second_stats['runs'] < first_stats['runs']:
                        match.winner = bowling_team
                        winner_message = f"{bowling_team.name} won by {first_stats['runs'] - second_stats['runs']} runs!"
                    else:
                        match.winner = None
                        winner_message = "Match ended in a tie!"

                    match.completed = True
                    match.save()
                    messages.success(request, f"Match completed! {win_msg}",extra_tags="match")
                    ball.save()  # Save the ball that completed the match
                    return redirect('record_ball', match_id=match.id)
            # if should_end_innings(batting_team_members, match) and is_second_innings:
            # # Determine which team batted first
            #     first_innings_team = match.team1 if match.current_innings == 2 else match.team2
            #     second_innings_team = match.team2 if match.current_innings == 2 else match.team1

            #     # Set the correct scores
            #     match.team1_score = first_stats['runs'] if match.team1 == first_innings_team else second_stats['runs']
            #     match.team2_score = second_stats['runs'] if match.team1 == first_innings_team else first_stats['runs']

            #     # Calculate wickets taken (assuming 10 wickets per team)
            #     wickets_lost = second_stats['wickets']
            #     total_players = batting_team.members.count()
            #     wickets_remaining = total_players - second_stats['wickets'] - 1

            #     # Determine winner
            #     if match.team1_score > match.team2_score:
            #         match.winner = match.team1
            #         win_msg = f"{match.team1.name} won by {match.team1_score - match.team2_score} runs!"
            #     elif match.team2_score > match.team1_score:
            #         match.winner = match.team2
            #         win_msg = f"{match.team2.name} won by {wickets_remaining} wickets!"
            #     else:
            #         match.winner = None
            #         win_msg = "The match ended in a tie!"

            #     match.completed = True
            #     match.save()
            #     messages.success(request, f"Match completed! {win_msg}")

            if form.cleaned_data.get('fielder'):
                fielder = Member.objects.get(id=form.cleaned_data['fielder'])
                ball.fielder = fielder.name

            # Handle dismissal
            if form.cleaned_data.get('is_catch') or form.cleaned_data.get('is_wicket') or form.cleaned_data.get('out_of_box'):
                dismissed_players.append(batsman.name)
                request.session[dismissed_players_key] = dismissed_players
                batting_team_members = batting_team.members.exclude(name__in=dismissed_players)

                if should_end_innings(batting_team_members, match):
                    if not is_second_innings:
                        request.session[batting_key] = bowling_team_id
                        request.session[bowling_key] = batting_team_id
                        request.session[innings_started_key] = True
                        request.session[dismissed_players_key] = []
                        match.current_innings = 2
                        match.save()
                        ball.save()
                        messages.success(
                            request,
                            f"First innings completed! {bowling_team.name} now batting and {batting_team.name} bowling",
                            extra_tags="innings"
                        )
                        return redirect('record_ball', match_id=match.id)
                    else:
                        match.completed = True
                        match.save()

            ball.save()
            return redirect('record_ball', match_id=match.id)

    else:
        # GET request
        form = BallEventForm(
            batting_team_members=batting_team_members,
            bowling_team_members=bowling_team_members,
            fielder_team_members=bowling_team_members,
            last_batsman_id=last_batsman_obj.id if last_batsman_obj else None,
            last_bowler_id=last_bowler_obj.id if last_bowler_obj else None,
            last_fielder_id=last_fielder_obj.id if last_fielder_obj else None,
        )




    # Get all ball events and calculate totals
    all_events = BallEvent.objects.filter(match=match).order_by('over', 'ball_in_over')

    # Separate innings based on the innings field
    first_innings_events = [e for e in all_events if e.innings == 1]
    second_innings_events = [e for e in all_events if e.innings == 2]
    is_second_innings = len(second_innings_events) > 0 or match.current_innings == 2
    # Calculate bowler statistics
    def calculate_bowler_stats(events):
        stats = defaultdict(lambda: {'balls': 0, 'runs': 0, 'wickets': 0})
        for ball in events:
            if ball.bowler:
                bowler = stats[ball.bowler]
                bowler['name'] = ball.bowler
                bowler['balls'] += 1
                bowler['runs'] += ball.runs
                if ball.is_catch or ball.is_wicket or ball.out_of_box:
                    bowler['wickets'] += 1

        # Convert to list and calculate derived stats
        result = []
        for name, data in stats.items():
            data['overs'] = f"{data['balls']//6}.{data['balls']%6}"
            data['economy'] = round((data['runs']*6)/data['balls'], 2) if data['balls'] else 0
            result.append(data)
        return result

    # Calculate innings stats
    # first_stats = calculate_innings_stats(first_innings_events,
    #                     len(dismissed_players) if not is_second_innings else 0)
    # second_stats = calculate_innings_stats(second_innings_events,
    #                     len(dismissed_players)) if is_second_innings else None
    first_runs = first_stats['runs'] if first_stats else 0
    second_runs = second_stats['runs'] if second_stats else 0


    # Check if second innings has won by surpassing first innings score
    second_innings_won = False

    # if is_second_innings and second_stats and first_stats and not match.completed:
    second_innings_won = False
    if is_second_innings and second_stats and first_stats:
        if second_stats['runs'] > first_stats['runs']:
            second_innings_won = True
            if not match.completed:  # Only update if not already completed
                match.winner = batting_team
                match.completed = True
                match.save()
                # Set winner message immediately
                winner_message = f"{batting_team.name} won by {10 - second_stats['wickets']} wickets"



    first_innings_bowlers = calculate_bowler_stats(first_innings_events)
    second_innings_bowlers = calculate_bowler_stats(second_innings_events) if is_second_innings else []

    # NEW: Calculate batter statistics
    def calculate_batter_stats(events):
        stats = defaultdict(lambda: {'balls': 0, 'runs': 0, '4s': 0, '6s': 0, 'out': False})
        for ball in events:
            if ball.batsman:
                batter = stats[ball.batsman]
                batter['name'] = ball.batsman
                batter['balls'] += 1
                batter['runs'] += ball.runs
                if ball.runs == 4:
                    batter['4s'] += 1
                if ball.runs == 6:
                    batter['6s'] += 1
                if ball.is_dismissal():  # If this ball dismissed the batter
                    batter['out'] = True
                    batter['out_desc'] = f"b {ball.bowler}"  # Simple dismissal description
        return list(stats.values())

    first_innings_batters = calculate_batter_stats(first_innings_events)
    second_innings_batters = calculate_batter_stats(second_innings_events) if is_second_innings else []

    # [Rest of the existing code remains the same until the context dictionary]



    # Calculate current innings status for both GET and POST requests
    current_innings_balls = BallEvent.objects.filter(
        match=match,
        innings=match.current_innings
    ).count()
    current_overs = current_innings_balls / 6
    # Auto-swap innings when over limit reached or if should end innings
    # With this:
    balls_per_innings = match.total_overs * 6
    if current_innings_balls >= balls_per_innings or should_end_innings(batting_team_members, match):
        if match.current_innings == 1:
            request.session[batting_key] = bowling_team_id
            request.session[bowling_key] = batting_team_id
            request.session[innings_started_key] = True
            request.session[dismissed_players_key] = []
            match.current_innings = 2
            match.save()
            messages.success(request, "Automatically switched to second innings",extra_tags="innings")
            return redirect('record_ball', match_id=match.id)
        else:
            match.completed = True
            match.save()
            messages.success(request, "Match completed due to over/batter limit.",extra_tags="match")


    # Over-by-over progression
    first_innings_over_runs = defaultdict(lambda: {'runs': 0, 'wickets': 0})
    second_innings_over_runs = defaultdict(lambda: {'runs': 0, 'wickets': 0})

    for ball in all_events:
        if ball.innings == 1:
            first_innings_over_runs[ball.over]['runs'] += ball.runs
            if ball.is_dismissal():
                first_innings_over_runs[ball.over]['wickets'] += 1
        elif ball.innings == 2:
            second_innings_over_runs[ball.over]['runs'] += ball.runs
            if ball.is_dismissal():
                second_innings_over_runs[ball.over]['wickets'] += 1

    # Determine winner message
    # Determine winner message if not already set
    # Determine winner message
    # After:
    winner_message = None
    if match.completed and first_stats:
        if is_second_innings and second_stats:
            # Two innings match
            total_players = batting_team.members.count()
            wickets_remaining = total_players - second_stats['wickets'] - 1

            if second_stats['runs'] > first_stats['runs']:
                winner_message = f"{batting_team.name} won by {wickets_remaining} wickets!"
            elif second_stats['runs'] < first_stats['runs']:
                winner_message = f"{bowling_team.name} won by {first_stats['runs'] - second_stats['runs']} runs!"
            else:
                winner_message = "Match ended in a tie!"
        else:
            # Single innings match
            winner_message = "Match completed after first innings"


    if is_second_innings and first_stats and not match.completed:
        target_score = first_stats['runs'] + 1  # Target is first innings total + 1
        runs_needed = max(0, target_score - second_stats['runs'])
    else:
        target_score = None
        runs_needed = None

    is_over_completed = (current_innings_balls > 0 and current_innings_balls + 1 % 6 == 0)

    if is_over_completed:
        over_number = (current_innings_balls + 1) // 6
        messages.success(request, f"Over {over_number} completed! Please change the bowler.", extra_tags="over_completed")
    context = {
        'form': form,
        'match': match,
        'teams': [match.team1, match.team2],
        'batting_team': batting_team,
        'bowling_team': bowling_team,
        'is_frozen': is_frozen,
        'is_second_innings': is_second_innings,
        'dismissed_players': dismissed_players,
        'winner_message': winner_message,
        'message': "🏁 Match Completed. No more balls can be recorded." if match.completed else None,
        'next_ball_number': (all_events.count() % 6) + 1,
        # 'over_run_map': dict(over_run_map),
        'second_innings_won': second_innings_won,
        'target_score': target_score,  # The target score (first innings + 1)
        'runs_needed': runs_needed,
        'team_size': batting_team.members.count(),
        'first_innings_balls': first_innings_balls,
        'second_innings_balls': second_innings_balls,
        'current_innings_balls': current_innings_balls,
        'first_innings_over_runs': dict(first_innings_over_runs),
        'second_innings_over_runs': dict(second_innings_over_runs),
        'is_over_completed': (current_innings_balls > 0 and current_innings_balls + 1 % 6 == 0),
        'ove': current_innings_balls +1 // 6,

        'innings': {
            'current': {
                'label': "Second Innings" if is_second_innings else "First Innings",
                'score': second_stats['score'] if is_second_innings else first_stats['score'],
                'runs': second_stats['runs'] if is_second_innings else first_stats['runs'],
                'wickets': second_stats['wickets'] if is_second_innings else first_stats['wickets'],
                'overs': second_stats['overs'] if is_second_innings else first_stats['overs'],
                'runs_to_win': (first_stats['runs'] + 1 - second_stats['runs'])
                              if is_second_innings and first_stats['runs'] > second_stats['runs'] else None,
                'target_score': target_score,
            'runs_needed': runs_needed,

            },
            'first': first_stats,
            'second': second_stats
        },
        'bowlers': {
            'first': first_innings_bowlers,
            'second': second_innings_bowlers
        },
        # NEW: Add batters to context
        'batters': {
            'first': first_innings_batters,
            'second': second_innings_batters
        }
    }

    return render(request, 'record_ball.html', context)


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Match, BallEvent

@login_required
def scorecard(request, match_id):
    match = get_object_or_404(Match, id=match_id, user=request.user)

    # Get all bowlers who have actually bowled in the match
    bowlers_in_match = BallEvent.objects.filter(match=match).values_list('bowler', flat=True).distinct()

    # Get all members from both teams
    team1_members = match.team1.members.values_list('name', flat=True)
    team2_members = match.team2.members.values_list('name', flat=True)
    all_members = sorted(set(team1_members.union(team2_members)))  # Unique sorted names

    # Get the selected bowler from request parameters
    selected_bowler = request.GET.get('bowler')

    # Filter events if a bowler is selected
    if selected_bowler:
        events = BallEvent.objects.filter(match=match, bowler=selected_bowler).order_by('over', 'ball_in_over')
    else:
        events = BallEvent.objects.filter(match=match).order_by('over', 'ball_in_over')

    # Calculate basic stats
    total_runs = sum(e.runs for e in events)
    total_balls = events.count()
    current_over = total_balls // 6
    current_ball = total_balls % 6

    # Calculate bowler stats if bowler is selected
    bowler_stats = {}
    if selected_bowler:
        bowler_events = events.filter(bowler=selected_bowler)
        balls = bowler_events.count()
        runs = sum(e.runs for e in bowler_events)
        wickets = bowler_events.filter(is_wicket=True).count()

        bowler_stats = {
            'overs': f"{balls//6}.{balls%6}",
            'runs': runs,
            'wickets': wickets,
            'economy': round(runs / (balls/6), 2) if balls > 0 else 0,
            'has_bowled': selected_bowler in bowlers_in_match  # Flag if this bowler has actually bowled
        }

    return render(request, 'scorecard.html', {
        'match': match,
        'events': events,
        'all_members': all_members,
        'bowlers_in_match': bowlers_in_match,
        'selected_bowler': selected_bowler,
        'bowler_stats': bowler_stats,
        'total_runs': total_runs,
        'total_overs': match.total_overs,
        'current_over': current_over,
        'current_ball': current_ball,
    })

from operator import itemgetter
from django.db.models import Sum, Count

@login_required
def leaderboard(request, match_id):
    match = get_object_or_404(Match, id=match_id, user=request.user)
    events = BallEvent.objects.filter(match=match)

    batter_scores = {}
    bowler_stats = {}

    for event in events:
        # Batting logic
        batter_scores[event.batsman] = batter_scores.get(event.batsman, 0) + event.runs

        # Bowling logic
        if event.bowler not in bowler_stats:
            bowler_stats[event.bowler] = {'runs': 0, 'wickets': 0, 'balls': 0}
        bowler_stats[event.bowler]['runs'] += event.runs
        bowler_stats[event.bowler]['balls'] += 1
        if event.is_catch:
            bowler_stats[event.bowler]['wickets'] += 1
    sorted_batters = sorted(batter_scores.items(), key=lambda x: x[1], reverse=True)
    # ✅ Best Batter by Most Runs
    best_batter = max(batter_scores.items(), key=lambda x: x[1], default=(None, 0))

    # ✅ Best Bowler by Wickets, then Economy
    def best_bowler_calc(bowler_stats):
        best = None
        for bowler, stats in bowler_stats.items():
            wickets = stats['wickets']
            runs = stats['runs']
            balls = stats['balls']
            economy = (runs / (balls / 6)) if balls else float('inf')

            if not best:
                best = (bowler, stats, economy)
            else:
                best_wickets = best[1]['wickets']
                best_economy = best[2]

                if wickets > best_wickets or (wickets == best_wickets and economy < best_economy):
                    best = (bowler, stats, economy)
        return best[:2] if best else (None, {'runs': 0, 'wickets': 0, 'balls': 0})

    best_bowler = best_bowler_calc(bowler_stats)

    return render(request, 'leaderboard.html', {
        'match': match,
        'batter_scores': batter_scores,
        'bowler_stats': bowler_stats,
        'best_batter': best_batter,
        'sorted_batters': sorted_batters,
        'best_bowler': best_bowler,
    })

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Team

@login_required
def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, user=request.user)

    if request.method == 'POST':
        new_name = request.POST.get('name')
        if new_name:
            team.name = new_name
            team.save()
            return redirect('start_match')  # or wherever you want to go after editing

    return render(request, 'edit.html', {'team': team})


@login_required
def swap_innings(request, match_id):
    match = get_object_or_404(Match, id=match_id, user=request.user)
    # Swap session values
    old_batting = request.session.get(f"match_{match_id}_batting")
    old_bowling = request.session.get(f"match_{match_id}_bowling")
    request.session[f"match_{match_id}_batting"] = old_bowling
    request.session[f"match_{match_id}_bowling"] = old_batting
    return redirect('record_ball', match_id=match.id)


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from .models import Match

@login_required
def delete_match(request, match_id):
    match = get_object_or_404(Match, id=match_id, user=request.user)
    if request.method == "POST":
        match.delete()
    return redirect('start_match')

from django.http import JsonResponse
from .models import Team

@login_required
def get_team_members(request, team_id):
    team = get_object_or_404(Team, id=team_id, user=request.user)
    members = team.members.values('id', 'name')
    return JsonResponse({'members': list(members)})


from django.db.models import Sum, Count
from collections import defaultdict
from django.shortcuts import render
from .models import BallEvent

def leaderboard_view(request):
    events = BallEvent.objects.all()

    # 🏏 Batsman Leaderboard
    batsman_stats = events.values('batsman').annotate(total_runs=Sum('runs')).order_by('-total_runs')
    best_batter = batsman_stats[0] if batsman_stats else None

    # 🎯 Bowler Stats (Wickets)
    bowler_stats_raw = events.filter(is_wicket=True).values('bowler').annotate(total_wickets=Count('id')).order_by('-total_wickets')

    # 📆 Economy Rate Calculation
    bowler_balls = defaultdict(int)
    bowler_runs = defaultdict(int)
    for ball in events:
        bowler_balls[ball.bowler] += 1
        bowler_runs[ball.bowler] += ball.runs

    economy_stats = []
    for bowler, balls in bowler_balls.items():
        overs = balls / 6 if balls else 1
        runs = bowler_runs[bowler]
        economy = runs / overs if overs > 0 else 0
        economy_stats.append({
            'bowler': bowler,
            'economy': round(economy, 2)
        })

    # Sort Economy in Descending Order (worst first)
    economy_stats.sort(key=lambda x: x['economy'], reverse=True)

    # 🔍 Best Bowler = wickets * 10 - economy
    bowler_scores = {}
    for stat in bowler_stats_raw:
        bowler_name = stat['bowler']
        wickets = stat['total_wickets']
        economy_data = next((e for e in economy_stats if e['bowler'] == bowler_name), None)
        economy = economy_data['economy'] if economy_data else 99
        score = (wickets * 10) - economy
        bowler_scores[bowler_name] = {
            'score': score,
            'wickets': wickets,
            'economy': economy,
            'runs': bowler_runs.get(bowler_name, 0),
            'balls': bowler_balls.get(bowler_name, 0)
        }

    best_bowler = max(bowler_scores.items(), key=lambda x: x[1]['score']) if bowler_scores else (None, None)

    # 🥤 Fielder Leaderboard
    fielder_stats = events.filter(is_catch=True).values('fielder').annotate(total_catches=Count('id')).order_by('-total_catches')

    return render(request, 'leaderboard_view.html', {
        'batsman_stats': batsman_stats,
        'bowler_stats': bowler_stats_raw,
        'economy_stats': economy_stats,
        'fielder_stats': fielder_stats,
        'best_batter': (best_batter['batsman'], best_batter['total_runs']) if best_batter else (None, None),
        'best_bowler': best_bowler  # (name, data_dict)
    })

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Tournament, Team, Match

@login_required
def start_tournament(request):
    user = request.user
    teams = Team.objects.filter(user=user)
    tournaments = Tournament.objects.filter(user=user).order_by('-created_at')

    if request.method == 'POST':
        name = request.POST.get('name')
        team_ids = request.POST.getlist('teams')
        total_overs = request.POST.get('total_overs')
        single_batting = 'single_batting' in request.POST

        if name and team_ids and total_overs and len(team_ids) >= 2:
            tournament = Tournament.objects.create(
                user=user,
                name=name,
                total_overs=int(total_overs),
                single_batting=single_batting
            )

            for team_id in team_ids:
                team = get_object_or_404(Team, id=team_id, user=user)
                tournament.teams.add(team)

            return redirect('tournament_detail', tournament_id=tournament.id)

    # Default values for new tournament
    total_overs = 4  # Default overs
    single_batting = False  # Default batting mode

    return render(request, 'start_tournament.html', {
        'teams': teams,
        'tournaments': tournaments,
        'total_overs': total_overs,
        'single_batting': single_batting
    })

# @login_required
# def tournament_detail(request, tournament_id):
#     tournament = get_object_or_404(Tournament, id=tournament_id, user=request.user)
#     matches = Match.objects.filter(tournament=tournament).order_by('-created_at')

#     return render(request, 'tournament_detail.html', {
#         'tournament': tournament,
#         'matches': matches
#     })
# views.py
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Tournament, Team, Match

@login_required
def tournament_detail(request, tournament_id):
    try:
        tournament = get_object_or_404(Tournament, id=tournament_id, user=request.user)
        teams = tournament.teams.all()
        matches = Match.objects.filter(tournament=tournament).order_by('-created_at')

        if request.method == 'POST':
            team1_id = request.POST.get('team1')
            team2_id = request.POST.get('team2')
            total_overs = request.POST.get('total_overs', tournament.total_overs)
            single_batting = request.POST.get('single_batting', 'off') == 'on'

            if team1_id and team2_id and total_overs:
                team1 = get_object_or_404(Team, id=team1_id, user=request.user)
                team2 = get_object_or_404(Team, id=team2_id, user=request.user)

                if team1 not in teams or team2 not in teams:
                    messages.error(request, "Selected teams must belong to this tournament")
                    return redirect('tournament_detail', tournament_id=tournament.id)

                match = Match.objects.create(
                    user=request.user,
                    team1=team1,
                    team2=team2,
                    tournament=tournament,
                    total_overs=int(total_overs),
                    single_batting=single_batting or tournament.single_batting
                )

                # Initialize session variables
                session_key = f"freeze_teams_{match.id}"
                batting_key = f"batting_team_{match.id}"
                bowling_key = f"bowling_team_{match.id}"
                innings_started_key = f"second_innings_started_{match.id}"
                dismissed_players_key = f"dismissed_players_{match.id}"

                request.session[batting_key] = team1.id
                request.session[bowling_key] = team2.id
                request.session[dismissed_players_key] = []
                request.session[innings_started_key] = False
                request.session[session_key] = False

                return redirect('record_ball', match_id=match.id)

        # Calculate leaderboard
        completed_matches = matches.filter(completed=True)
        leaderboard = calculate_leaderboard(teams, completed_matches)

        # Generate team pairings
        team_pairings = []
        team_list = list(teams)
        for i in range(len(team_list)):
            for j in range(i+1, len(team_list)):
                team_pairings.append((team_list[i], team_list[j]))

        # Get all matches grouped by status
        upcoming_matches = [pair for pair in team_pairings if not matches.filter(
            Q(team1=pair[0], team2=pair[1]) | Q(team1=pair[1], team2=pair[0])
        ).exists()]

        in_progress_matches = matches.filter(completed=False)
        completed_matches = matches.filter(completed=True)

        context = {
            'tournament': tournament,
            'matches': matches,
            'teams': teams,
            'leaderboard': leaderboard,
            'team_pairings': team_pairings,
            'upcoming_matches': upcoming_matches,
            'in_progress_matches': in_progress_matches,
            'completed_matches': completed_matches,
            'single_batting': tournament.single_batting,
            'total_overs': tournament.total_overs
        }

        return render(request, 'tournament_detail.html', context)

    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('start_tournament')
def calculate_leaderboard(teams, matches):
    leaderboard = []

    for team in teams:
        leaderboard.append({
            'team': team,
            'matches_played': 0,
            'matches_won': 0,
            'matches_lost': 0,
            'matches_drawn': 0,
            'points': 0,
            'total_runs_scored': 0,
            'total_overs_faced': 0,
            'total_runs_conceded': 0,
            'total_overs_bowled': 0,
            'net_run_rate': 0.0
        })

    for match in matches.filter(completed=True):
        team1_data = next((t for t in leaderboard if t['team'] == match.team1), None)
        team2_data = next((t for t in leaderboard if t['team'] == match.team2), None)

        if team1_data and team2_data:
            # Update matches played
            team1_data['matches_played'] += 1
            team2_data['matches_played'] += 1

            # Update runs and overs
            team1_score = match.team1_score if match.team1_score is not None else 0
            team2_score = match.team2_score if match.team2_score is not None else 0
            overs = match.total_overs if match.total_overs is not None else 0

            team1_data['total_runs_scored'] += team1_score
            team1_data['total_overs_faced'] += overs
            team1_data['total_runs_conceded'] += team2_score
            team1_data['total_overs_bowled'] += overs

            team2_data['total_runs_scored'] += team2_score
            team2_data['total_overs_faced'] += overs
            team2_data['total_runs_conceded'] += team1_score
            team2_data['total_overs_bowled'] += overs

            # Update points based on winner
            if match.winner == match.team1:
                team1_data['matches_won'] += 1
                team1_data['points'] += 2
                team2_data['matches_lost'] += 1
            elif match.winner == match.team2:
                team2_data['matches_won'] += 1
                team2_data['points'] += 2
                team1_data['matches_lost'] += 1
            else:  # Draw
                team1_data['matches_drawn'] += 1
                team2_data['matches_drawn'] += 1
                team1_data['points'] += 1
                team2_data['points'] += 1

    # Calculate NRR and sort
    for team in leaderboard:
        try:
            runs_for = team['total_runs_scored']
            overs_faced = team['total_overs_faced'] or 0.1
            runs_against = team['total_runs_conceded']
            overs_bowled = team['total_overs_bowled'] or 0.1

            team['net_run_rate'] = round((runs_for/overs_faced) - (runs_against/overs_bowled), 2)
        except ZeroDivisionError:
            team['net_run_rate'] = 0.0

    leaderboard.sort(key=lambda x: (-x['points'], -x['net_run_rate']))
    return leaderboard
@login_required
def delete_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id, user=request.user)
    if request.method == 'POST':
        tournament.delete()
        return redirect('tournament')
    return redirect('tournament_detail', tournament_id=tournament_id)
@login_required
def tournament_leaderboard(request, tournament_id):
    try:
        # Get tournament and basic match data
        tournament = get_object_or_404(Tournament, id=tournament_id, user=request.user)
        teams = tournament.teams.all()
        matches = Match.objects.filter(tournament=tournament)
        completed_matches = matches.filter(completed=True)

        # ===== TEAM STANDINGS CALCULATION =====
        team_stats = {}
        for team in teams:
            team_stats[team.id] = {
                'team': team,
                'matches_played': 0,
                'matches_won': 0,
                'matches_lost': 0,
                'matches_drawn': 0,
                'points': 0,
                'runs_scored': 0,
                'overs_faced': 0,
                'runs_conceded': 0,
                'overs_bowled': 0,
                'net_run_rate': 0.0  # Initialize NRR
            }

        for match in completed_matches:
            # Skip matches that don't have both teams in the tournament
            if match.team1 not in teams or match.team2 not in teams:
                continue

            team1_stats = team_stats.get(match.team1.id)
            team2_stats = team_stats.get(match.team2.id)

            if not team1_stats or not team2_stats:
                continue

            # Update matches played
            team1_stats['matches_played'] += 1
            team2_stats['matches_played'] += 1

            # Update runs and overs (with None checks)
            team1_score = match.team1_score if match.team1_score is not None else 0
            team2_score = match.team2_score if match.team2_score is not None else 0
            overs = match.total_overs if match.total_overs is not None else 0

            team1_stats['runs_scored'] += team1_score
            team1_stats['overs_faced'] += overs
            team1_stats['runs_conceded'] += team2_score
            team1_stats['overs_bowled'] += overs

            team2_stats['runs_scored'] += team2_score
            team2_stats['overs_faced'] += overs
            team2_stats['runs_conceded'] += team1_score
            team2_stats['overs_bowled'] += overs

            # Update wins/losses/draws and points
            if match.winner == match.team1:
                team1_stats['matches_won'] += 1
                team1_stats['points'] += 2
                team2_stats['matches_lost'] += 1
            elif match.winner == match.team2:
                team2_stats['matches_won'] += 1
                team2_stats['points'] += 2
                team1_stats['matches_lost'] += 1
            else:  # Draw
                team1_stats['matches_drawn'] += 1
                team2_stats['matches_drawn'] += 1
                team1_stats['points'] += 1
                team2_stats['points'] += 1

        # Calculate Net Run Rate (NRR) for each team
        # In your team stats calculation
        for stats in team_stats.values():
            try:
                runs_for = stats['runs_scored']
                overs_faced = stats['overs_faced'] or 0.1  # Avoid division by zero
                runs_against = stats['runs_conceded']
                overs_bowled = stats['overs_bowled'] or 0.1

                run_rate_for = runs_for / overs_faced
                run_rate_against = runs_against / overs_bowled
                stats['net_run_rate'] = round(run_rate_for - run_rate_against, 2)
            except (ZeroDivisionError, TypeError):
                stats['net_run_rate'] = 0.0

        # Sort team leaderboard by points then NRR
        team_leaderboard = sorted(
            team_stats.values(),
            key=lambda x: (-x['points'], -x['net_run_rate'])
        )

        # ===== PLAYER STATISTICS CALCULATION =====
        # Get all ball events for this tournament
        ball_events = BallEvent.objects.filter(match__tournament=tournament)

        # 🏏 Batsman Leaderboard (Top 5)
        batsman_stats = []
        if ball_events.exists():
            batsman_stats = ball_events.values('batsman').annotate(
                total_runs=Sum('runs'),
                balls_faced=Count('id')
            ).order_by('-total_runs')[:5]

            # Calculate strike rates
            for batsman in batsman_stats:
                balls = batsman['balls_faced']
                runs = batsman['total_runs']
                batsman['strike_rate'] = round((runs / balls) * 100, 2) if balls > 0 else 0

        # 🎯 Bowler Leaderboard (Top 5 by wickets)
        # In your tournament_leaderboard view
        bowler_stats = []
        bowler_data = {}
        if ball_events.exists():
            # Get all bowlers who have been involved in any dismissal
            bowler_stats = ball_events.filter(
                Q(is_wicket=True) | Q(is_catch=True) | Q(out_of_box=True)
            ).values('bowler').annotate(
                bowled_wickets=Count('id', filter=Q(is_wicket=True)),
                caught_wickets=Count('id', filter=Q(is_catch=True)),
                total_balls=Count('id'),
                total_runs=Sum('runs')
            ).order_by('-bowled_wickets')[:5]

            # Calculate bowler statistics
            for bowler in bowler_stats:
                bowler_name = bowler['bowler']
                balls = bowler['total_balls']
                runs = bowler['total_runs']
                bowled = bowler['bowled_wickets']
                caught = bowler['caught_wickets']

                overs = balls / 6 if balls else 0.1
                economy = (runs / overs) if overs > 0 else 0

                bowler_data[bowler_name] = {
                    'wickets': bowled + caught,  # Total wickets (bowled + caught)
                    'economy': round(economy, 2),
                    'runs_conceded': runs,
                    'overs_bowled': round(overs, 1),
                    'bowled': bowled,
                    'caught': caught
                }

        # 🥤 Fielder Leaderboard (Top 5)
        fielder_stats = []
        if ball_events.exists():
            fielder_stats = ball_events.filter(is_catch=True).values(
                'fielder'
            ).annotate(
                total_catches=Count('id')
            ).order_by('-total_catches')[:5]

        context = {
            'tournament': tournament,
            'leaderboard': team_leaderboard,
            'matches': matches,
            'completed_matches': completed_matches.count(),
            'batsman_stats': batsman_stats,
            'bowler_stats': bowler_stats,
            'bowler_data': bowler_data,
            'fielder_stats': fielder_stats,
        }

        return render(request, 'tournament_leaderboard.html', context)

    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in tournament_leaderboard: {str(e)}", exc_info=True)

        # Return a meaningful error response
        return render(request, 'error.html', {
            'error_message': "An error occurred while generating the leaderboard. Please try again later."
        }, status=500)