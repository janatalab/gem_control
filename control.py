# control.py
#
# Methods for setting state during Groove Enhancement Machine (GEM) experiments


from django.contrib.auth.decorators import login_required

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseGone
from django.shortcuts import render

import polling2

from pyensemble.models import GroupSession

from .forms import ExperimentInitForm, TrialInitForm

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

            # Get the group session
            session = GroupSession.objects.get(pk=session_id)

            # Create our context dict from the parameters specified in the form
            params = form.cleaned_data

            # # Generate our trial list (essentialy a timeline)
            # trial_list
            # if params['trial_generator'] == 'fully_random':
            #     # Get our alpha levels
            #     alphas = params['metronome_alpha']

            #     # Get our number of repeats
            #     num_repeats = params['repeats']

            # params.update({'trial_list': trial_list})

            # Initialize our current context
            current_context = {
                'trial_num' = 0,
            }

            params.update('current': current_context)

            # Cache our parameters and trial lists to our session cache
            request.session[session.get_cache_key()]['params'] = params
            request.session.modified=True

            # Write current experiment context to the group session context (this is what the participant sessions poll to obtain state)
            session.context = current_context

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


@login_required
def init_trial(request, session_id):
    if request.method == 'POST':
        form = TrialInitForm(request.POST)

        if form.is_valid():
            # Get the group session
            session = GroupSession.objects.get(pk=session_id)

            current_params = form.cleaned_data

            # Perform some validation based on designated trial number and cached info
            session_params = request.session[session.get_cache_key()]
            cached_trialnum = session_params['current']['trial_num']

            if current_params['trial_num'] != cached_trialnum+1:
                # Return a trial number error. (This should probably be implemented in form field validation)
                return HttpResponseBadRequest()

            # Wait until all participants have responded for the cached trial
            try:
                polling2.poll(session.responding_complete(cached_trialnum), step=0.5, timeout=60)
            except:
                return HttpResponseGone()

            session_params['current']['trial_num'] += 1
            request.session[session.get_cache_key()] = session_params
            request.session.modified=True

            # Set group session context
            current_params.update({'state':'ready'})
            session.context = current_params
            session.save()

            return HttpResponse(status=202)

    else:
        form = TrialInitForm()

    template = 'gem_pyens_example/init_trial.html'
    context = {
        'form': form
    }

    return render(request, template, context)


@login_required
def start_trial(request, session_id):
    set_session_state(request, session_id, 'running')

    return HttpResponse(status=200)


@login_required
def end_trial(request, session_id):
    set_session_state(request, session_id, 'ended')

    return HttpResponse(status=200)


def set_session_state(request, session_id, state):
    # Get the group session
    session = GroupSession.objects.get(pk=session_id)

    # Set the session state
    context = session.context
    context.update({'state': state})
    session.context = context
    session.save()