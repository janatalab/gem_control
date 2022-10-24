# urls.py

from django.urls import path

from . import control, create

app_name='gem_control'

urlpatterns = [
    path('create/experiment/', create.create_test_experiment, name='create_experiment'),
    path('control/experiment/init/', control.init_experiment, name='init_experiment'),
    path('control/experiment/end/', control.end_experiment, name='end_experiment'),
    path('control/trial/init/', control.init_trial, name='init_trial'),
    path('control/trial/start/', control.start_trial, name='start_trial'),
    path('control/trial/end/', control.end_trial, name='end_trial'),
]

