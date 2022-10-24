# control.py
#
# Methods for setting state during Groove Enhancement Machine (GEM) experiments

from django.conf import settings
from django.contrib.auth.decorators import login_required

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseGone
from django.shortcuts import render

import polling2

from pyensemble.models import Session
from pyensemble.group.models import GroupSession, GroupSessionSubjectSession
from pyensemble.group import views as group_views

from .forms import ExperimentInitForm, TrialInitForm

import pdb

''' 
A view to initialize the experiment. Rather than having this view pull separately from the experiment presets, 
have the caller, i.e. the GEM GUI request this view and then populate it with its own conception of 
the presets that it uses when it initializes and runs the experiment in non-PyEnsemble mode. 
Setting things up this way also sets the stage for allowing the client to set the specific parameters on the fly,
and helps keep the control mechanisms abstract.
'''

@login_required
def init_experiment(request):
    if request.method == 'POST':
        form = ExperimentInitForm(request.POST)

        if form.is_valid():
            # Get the group session object
            session = group_views.get_group_session(request)

            # Create our context dict from the parameters specified in the form
            params = form.cleaned_data

            # Initialize our current context
            context = {
                'trial_num': 0,
                'state': 'initialized',
            }

            # Cache our parameters and trial lists to our session cache
            cache_key = session.get_cache_key()
            request.session[cache_key]['params'] = params
            request.session[cache_key]['context'] = context
            request.session.modified=True

            # Write current experiment context to the group session context (this is what the participant sessions poll to obtain state)
            session.context = context

            # Write our parameters to the session parameters
            session.params = params

            # Write our initalized state to the group session object
            session.state = session.States.RUNNING

            # Save the group session object
            session.save()

            # Return success
            return HttpResponse(status=202)

    else:
        form = ExperimentInitForm()

    template = 'gem_control/init_experiment.html'
    context = {
        'form': form
    }

    return render(request, template, context)

def end_experiment(request):
    response = group_views.end_groupsession(request)

    return HttpResponse(response)

@login_required
def init_trial(request):
    # Get the group session object
    session = group_views.get_group_session(request)

    if request.method == 'POST':
        form = TrialInitForm(request.POST)

        if form.is_valid():
            current_params = form.cleaned_data

            # Perform some validation based on designated trial number and cached info
            # session_params = request.session[session.get_cache_key()]
            cached_trialnum = session.context['trial_num']

            if current_params['trial_num'] != cached_trialnum+1:
                # Return a trial number error. (This should probably be implemented in form field validation)
                return HttpResponseBadRequest()

            # Wait until all participants are ready again on their clients
            group_ready = session.wait_group_ready_client()

            if not group_ready:
                return HttpResponseGone()

            # Set group session context
            current_params.update({'state':'trial:initialized'})
            session.context = current_params
            session.save()

            return HttpResponse(status=202)

    else:
        form = TrialInitForm()

        # Set group session context
        session.context.update({'state':'trial:initializing'})
        session.save()

    template = 'gem_control/init_trial.html'
    context = {
        'form': form
    }

    return render(request, template, context)

# We aren't performing any special handling during either the starting or stopping of a trial, so just pass the requests along
@login_required
def start_trial(request):
    response = group_views.start_trial(request)

    return response

@login_required
def end_trial(request):
    response = group_views.end_trial(request)

    return response
  