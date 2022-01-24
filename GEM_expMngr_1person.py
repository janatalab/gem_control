'''
Presets for use in single player GEM pilot experiment.

This experiment involves solo tapper with adaptive metronome to make
sure that we can replicate the single-tapper results of Fairhurst, Janata, and
Keller (2013) with the GEM system.

    IV: alpha value
    DV: std asynchrony; subjective ratings
    Instructions: Listen to first 2 metronome tones and then synchronize

Authors: Lauren Fink, Scottie Alexander, Petr Janata
Contact: pjanata@ucdavis.edu
Repository link: https://github.com/janatalab/GEM
'''

import os, sys, re

# Deal with adding the requisite GEM GUI modules to the path
if not os.environ.get('GEMROOT', None):
    # Try to get the GEM path from this module's path.
    p = re.compile('.*/GEM/')
    m = p.match(os.path.join(os.path.abspath(os.path.curdir),__file__))
    if m:
        os.environ['GEMROOT'] = m.group(0)

sys.path.append(os.path.join(os.environ['GEMROOT'],'GUI'))

from GEMGUI import GEMGUI
from GEMIO import get_master_port

presets = {
    "serial": {"port": get_master_port(), "baud_rate": 115200, "timeout": 5},
    "filename": "GEM_1playerPilot",
    "data_dir": "/Users/" + os.environ['USER'] + "/Desktop/GEM_data/1person_GEM_pilotData/",
    "hfile": os.path.join(os.environ['GEMROOT'], "GEM/GEMConstants.h"),
    "slaves_requested": 1,
    "metronome_alpha": [0, 0.25, 0.5, 0.75, 1],
    "metronome_tempo": 120.0, #units: beats-per-minute
    "repeats": 10, #10, #number of rounds at each alpha; Fairhurst was 12
    "windows": 26, #26, #number of metronome clicks; Fairhurst = 24
    "audio_feedback": ["hear_metronome"],
    "metronome_heuristic": ["average"],
    "connect_pyensemble": True,
    "pyensemble_server": "http://localhost:8000",
}

if __name__ == "__main__":
    g = GEMGUI(presets)
    g.mainloop()
