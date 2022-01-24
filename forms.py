# forms.py

import django.forms as forms
from django.core.validators import MaxValueValidator, MinValueValidator 

from .settings import GEM_SETTINGS

class ExperimentInitForm(forms.Form):
    slaves_requested = forms.IntegerField(initial=1, validators=[MinValueValidator(1), MaxValueValidator(GEM_SETTINGS['max_tappers'])])

    metronome_alpha = forms.JSONField()
    metronome_tempo = forms.FloatField(initial=120.0)   #units: beats-per-minute
    repeats = forms.IntegerField(initial=10, validators=[MinValueValidator(1)])    #number of rounds at each alpha
    windows = forms.IntegerField(initial=26, validators=[MinValueValidator(1)])    #number of metronome clicks; Fairhurst = 24
    audio_feedback = forms.ChoiceField(choices=GEM_SETTINGS['feedback_options'])

    trial_generator = forms.CharField(initial='fully_random')  # either a keyword string, e.g. 'fully_random', or a module and method for generating a trial list

class TrialInitForm(forms.Form):
    trial_num = forms.IntegerField()
    params = forms.JSONField()