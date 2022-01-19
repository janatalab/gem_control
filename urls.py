# urls.py

from django.urls import path

from . import control

app_name='gem_control'

urlpatterns = [
    path('control/experiment/init/<int:session_id>/', control.init_experiment, name='init_experiment'),
    path('control/experiment/end/<int:session_id>/', control.end_experiment, name='end_experiment'),
    path('control/trial/init/<int:session_id>/', control.init_trial, name='init_trial'),
    path('control/trial/start/<int:session_id>/', control.start_trial, name='start_trial'),
    path('control/trial/end/<int:session_id>/', control.end_trial, name='end_trial'),
    path('control/trial/state/<int:session_id>/', control.trial_state, name='trial_state'),
]

