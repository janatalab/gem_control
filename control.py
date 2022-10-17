# control.py
#
# Methods for setting state during Groove Enhancement Machine (GEM) experiments


from django.contrib.auth.decorators import login_required

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseGone
from django.shortcuts import render

import polling2

from pyensemble.models import Session
from pyensemble.group.models import GroupSession, GroupSessionSubjectSession
from pyensemble.group.views import get_session_id

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
            # Get the session ID from the session cache
            session_id = get_session_id(request)

            # Get the group session
            session = GroupSession.objects.get(pk=session_id)

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
    # Get the session ID from the session cache
    session_id = get_session_id(request)

    # Get the group session
    session = GroupSession.objects.get(pk=session_id)

    session.state = session.States.COMPLETED
    session.save()

    return HttpResponse(status=200)

@login_required
def init_trial(request):
    if request.method == 'POST':
        form = TrialInitForm(request.POST)

        if form.is_valid():
            # Get the session ID from the session cache
            session_id = get_session_id(request)

            # Get the group session
            session = GroupSession.objects.get(pk=session_id)

            current_params = form.cleaned_data

            # Perform some validation based on designated trial number and cached info
            # session_params = request.session[session.get_cache_key()]
            cached_trialnum = session.context['trial_num']

            if current_params['trial_num'] != cached_trialnum+1:
                # Return a trial number error. (This should probably be implemented in form field validation)
                return HttpResponseBadRequest()

            # Wait until all participants have responded for the cached trial
            try:
                polling2.poll(session.group_ready, step=0.5, timeout=60)
            except:
                return HttpResponseGone()

            # Set group session context
            current_params.update({'state':'ready'})
            session.context = current_params
            session.save()

            return HttpResponse(status=202)

    else:
        form = TrialInitForm()

    template = 'gem_control/init_trial.html'
    context = {
        'form': form
    }

    return render(request, template, context)

# Method to indiciate participant readiness and wait until all participants have indicated readiness
def set_user_ready(request):
    # Get the group session ID from the session cache
    groupsession_id = get_session_id(request)

    # Get the group session
    group_session = GroupSession.objects.get(pk=groupsession_id)

    # Get the experiment info from the cache
    expsessinfo = request.session[group_session.experiment.get_cache_key()]

    # Get the user session
    user_session = Session.objects.get(pk=expsessinfo['session_id'])

    # Get the conjoint group and user session entry
    gsus = GroupSessionSubjectSession.objects.get(group_session=group_session, user_session=user_session)

    # Set the state of this user to READY 
    gsus.state = gsus.States.READY
    gsus.save()

    return True

@login_required
def start_trial(request):
    set_session_state(request, 'running')

    return HttpResponse(status=200)


@login_required
def end_trial(request):
    set_session_state(request, 'ended')

    return HttpResponse(status=200)


def get_session_state(request):
    # Get the session ID from the session cache
    session_id = get_session_id(request)

    # Get the group session
    session = GroupSession.objects.get(pk=session_id)

    if not session.context:
        state = 'undefined'
    else:
        state = session.context['state']

    return state


def set_session_state(request, state):
    # Get the session ID from the session cache
    session_id = get_session_id(request)

    # Get the group session
    session = GroupSession.objects.get(pk=session_id)

    # Set the session state
    context = session.context
    context.update({'state': state})
    session.context = context
    session.save()