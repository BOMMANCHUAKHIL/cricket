from django import forms
from .models import Member
# class TeamSplitForm(forms.Form):
#     TEAM_CHOICES = (
#         (2, '2 Teams'),
#         (3, '3 Teams'),
#         (4, '4 Teams'),
#         (5, '5 Teams'),
#     )
#     max_shuffle = forms.IntegerField(
#         min_value=1,
#         label="Maximum shuffle group size",
#         help_text="Members will be shuffled in groups of this size before distribution"
#     )
#     num_teams = forms.ChoiceField(choices=TEAM_CHOICES, label="Select Number of Teams", widget=forms.Select)
#     # members = forms.CharField(
#     #     widget=forms.Textarea,
#     #     label="Member Names",
#     #     help_text="Enter one member name per line"
#     # )
#     members = forms.ModelMultipleChoiceField(
#         queryset=Member.objects.all(),
#         widget=forms.CheckboxSelectMultiple(attrs={
#             'class': 'form-check-input',
#         }),
#         label="Select Members"
#     )


class TeamSplitForm(forms.Form):
    TEAM_CHOICES = (
        (2, '2 Teams'),
        (3, '3 Teams'),
        (4, '4 Teams'),
        (5, '5 Teams'),
    )
    max_shuffle = forms.IntegerField(
        min_value=1,
        label="Maximum shuffle group size",
        help_text="Members will be shuffled in groups of this size before distribution"
    )
    num_teams = forms.ChoiceField(choices=TEAM_CHOICES, label="Select Number of Teams", widget=forms.Select)

    members = forms.ModelMultipleChoiceField(
        queryset=Member.objects.none(),  # default empty
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Select Members"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')  # get user from view
        super().__init__(*args, **kwargs)
        self.fields['members'].queryset = Member.objects.filter(user=user)

from django import forms
from .models import Member

class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter member name'}),
        }
class MemberPairForm(forms.Form):
    name1 = forms.CharField(label="First Member Name", max_length=100)
    name2 = forms.CharField(label="Second Member Name", max_length=100)

# from django import forms
# from .models import BallEvent, Member

# class BallEventForm(forms.ModelForm):
#     class Meta:
#         model = BallEvent
#         fields = ['over', 'ball_in_over', 'batsman', 'bowler', 'runs', 'is_catch', 'fielder']
from django import forms
from .models import BallEvent
class BallEventForm(forms.ModelForm):


    class Meta:
        model = BallEvent
        fields = ['batsman', 'bowler', 'runs', 'is_catch', 'is_wicket', 'out_of_box', 'fielder']
        widgets = {
            'is_catch': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_wicket': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'out_of_box': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'runs': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        batting_team_members = kwargs.pop('batting_team_members', [])
        bowling_team_members = kwargs.pop('bowling_team_members', [])
        fielder_team_members = kwargs.pop('fielder_team_members', [])
        last_batsman_id = kwargs.pop('last_batsman_id', None)
        last_bowler_id = kwargs.pop('last_bowler_id', None)
        last_fielder_id = kwargs.pop('last_fielder_id', None)
        super().__init__(*args, **kwargs)

        super().__init__(*args, **kwargs)

        # Set up batsman field with filtered members
        if batting_team_members is not None:
            self.fields['batsman'].widget = forms.Select(
                attrs={'class': 'form-select'},
                choices=[('', '-- Select Batsman --')] + [(m.id, m.name) for m in batting_team_members]
            )
        else:
            self.fields['batsman'].widget = forms.Select(attrs={'class': 'form-select'})
        self.fields['bowler'].widget = forms.Select(
            choices=[(m.id, m.name) for m in bowling_team_members]
        )
        self.fields['fielder'].widget = forms.Select(
            choices=[(m.id, m.name) for m in fielder_team_members]
        )
        self.fields['fielder'].required = False

        # ✅ Set default selected batsman and bowler
        if last_batsman_id:
            self.initial['batsman'] = last_batsman_id
        if last_bowler_id:
            self.initial['bowler'] = last_bowler_id
        if last_fielder_id:
            self.initial['fielder'] = last_fielder_id
        def clean(self):
            cleaned_data = super().clean()
            is_catch = cleaned_data.get('is_catch')
            fielder = cleaned_data.get('fielder')

            # Validate that fielder is selected when catch is checked
            if is_catch and not fielder:
                self.add_error('fielder', 'Please select a fielder for catch out')

            return cleaned_data
