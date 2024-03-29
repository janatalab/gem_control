# create.py
#
# Module for creating GEM experiments programmatically

from pyensemble.models import DataFormat, Question, Form, FormXQuestion, ExperimentXForm, Experiment

from django.http import HttpResponse

def create_test_experiment(request):
    # Instantiates necessary response options, questions, forms, and experiment to test running a GEM group experiment.

    # Create the experiment object
    eo, created = Experiment.objects.get_or_create(title='GEM Test', is_group=True)

    # Define some data formats as a list of dictionaries
    data_formats = [
        {
            'df_type': 'enum',
            'enum_values': '"Yes","No"',
        },
        {
            'df_type': 'enum',
            'enum_values': '"Strongly Disagree","Somewhat Disagree","Neither Agree nor Disagree","Somewhat Agree","Strongly Agree"',
        },
        {
            'df_type': 'int',
        }
    ]

    # Upload the data formats
    for df in data_formats:
        dfo, created = DataFormat.objects.get_or_create(**df)

        if df.get('enum_values','').find('Disagree'):
            disagree_df = dfo

    # Define some question data as a list of dictionaries
    question_data = [
        {
            'text': 'I experienced this trial to be difficult.',
            'data_format': disagree_df,
            'html_field_type': 'radiogroup'
        }
    ]

    for q in question_data:
        qo, created = Question.objects.get_or_create(**q)

    # Define form data, including data that we will populate ExperimentXForm with
    form_data = [
        {
            'name': 'Start Session',
            'questions': [],
            'form_handler': 'form_subject_register'
        },
        {
            'name': 'GEM Post Trial',
            'questions': [qo],
            'form_handler': 'group_trial'
        },
        {
            'name': 'End Session',
            'questions': [],
            'form_handler': 'form_end_session'
        }
    ]

    # Delete any existing ExperimentXForm entries for this experiment
    ExperimentXForm.objects.filter(experiment=eo).delete()

    for fidx, f in enumerate(form_data, start=1):
        fo, created = Form.objects.get_or_create(name=f['name'])

        for idx, q in enumerate(f['questions'], start=1):
            fqo, created = FormXQuestion.objects.get_or_create(form=fo, question=q, form_question_num=idx)

        # Link the form into the experiment, implementing some looping logic along the way
        goto = None
        repeat = None
        stimulus_script = ''

        # Trial initialization
        if f['name'] == 'GEM Post Trial':
            stimulus_script = 'gem_control.control.init_trial()'

        # Looping logic
        if f['name'] == 'GEM Post Trial':
            goto = [f['name'] for f in form_data].index('GEM Post Trial')+1
            repeat = 10

        efo, created = ExperimentXForm.objects.get_or_create(
            experiment=eo,
            form = fo,
            form_order = fidx,
            form_handler = f['form_handler'],
            goto = goto, # want to make this more dynamic if we add more forms to this example
            repeat = repeat,
            stimulus_script = stimulus_script
            )


    return HttpResponse('create_test_experiment: success')
