# settings.py
#
# This module may be obsolete because we want to rely on a single point of experiment parameter specification, which in this case in the presets variable in the file that is used to launch the experiment-specific GEM GUI

GEM_SETTINGS = {
    'max_tappers': 4,
    'feedback_options': [
        ("hear_metronome", "Hear Metronome"),
        ("hear_self", "Hear Self"),
        ("hear_metronome_and_self", "Hear Metronome and Self"),
        ("hear_all", "Hear All"),
    ],
}