# file.py

GEM_MAX_TAPPERS = 4 # should match value specified in GEM/GEMConstants.h

import storages
import json

import pandas as pd

import pdb

# GEMDataFileReader is based on GEMDataFile from GEM/GUI/GEMIO.py
class GEMDataFileReader:
    def __init__(self, filepath):
        self.filepath = filepath

        # Open the file
        self.is_open = False
        self.open()

        # Read the file
        self.read_file()

    def open(self):
        mode = 'rb'
        if not self.is_open:
            if isinstance(self.filepath, storages.backends.s3.S3File):
                self._io = self.filepath.open(mode)
            else:
                self._io = open(filepath, mode)

            self.is_open = True
            self.ptr = 0

    def close(self):
        if self.is_open:
            self.ptr = self._io.tell()
            self._io.close()
            self._io = None
            self.is_open = False

    def reopen(self):
        if not self.is_open:
            if isinstance(self.filepath, storages.backends.s3.S3File):
                self._io = self.filepath.open("rb")
            else:
                self._io = open(self.filepath, "rb")

            self._io.seek(self.ptr, 0)
            self.is_open = True

    def read_header(self, offset):
        self.reopen()
        self._io.seek(offset, 0)

        # Read the header length, stored as a uint64
        nel_uint64 = int.from_bytes(self._io.read(8),"little")

        # Read the header
        hdr_str = self._io.read(nel_uint64)

        # Convert to a dict
        hdr_dict = json.loads(hdr_str)

        return hdr_dict

    def read_file_header(self):
        offset = 0
        self.file_hdr = self.read_header(offset)

        # Determine the number of runs based on full combination of conditions
        if "nruns" not in self.file_hdr.keys():
            self.nruns = len(self.file_hdr["metronome_alpha"])*len(self.file_hdr["metronome_tempo"])*self.file_hdr["repeats"]

        # Read the run offset information
        self.idx_map_offset = self._io.tell()

        self.run_offsets = []
        self.run_info = []

        for r in range(0, self.nruns):
            self.run_offsets.append(int.from_bytes(self._io.read(8), "little"))
            self.run_info.append(GEMRun(self))

    def read_run_header(self, krun):
        # Read the file header and run offsets if we haven't yet
        if not self.run_offsets:
            self.read_file_header()

        offset = self.run_offsets[krun]

        # Check for valid run offset (>0)
        if offset:
            self.run_info[krun].hdr = self.read_header(offset)

        return self.run_info[krun].hdr


    def read_run_data(self, krun):
        # Get our run offset
        run_offset = self.run_offsets[krun]

        # Only read data if we have data
        if run_offset:
            run_data = []

            # Seek to the start of the run
            self._io.seek(run_offset, 0)

            # Read the header length, stored as a uint64
            nel_uint64 = int.from_bytes(self._io.read(8),"little")

            # Seek to the start of the run data
            self._io.seek(self.run_offsets[krun]+8+nel_uint64, 0)

            # Iterate over windows
            for window_idx in range(0, self.file_hdr['windows']):
                window_data = {}

                # Get the packet content identifier
                window_data['dtp_id'] = self._io.read(1)

                # Get the serial number of the metronome tone
                window_data['window_num'] = int.from_bytes(self._io.read(2), "little")

                # Get the time of the metronome tone
                window_data['met_time'] = int.from_bytes(self._io.read(4), "little")

                # Get the tapper asynchronies
                window_data['asynchronies'] = []
                for tapper in range(0, GEM_MAX_TAPPERS):
                    window_data['asynchronies'].append(int.from_bytes(self._io.read(2), "little", signed=True))

                # Read the nex metronome adjustment
                window_data['next_met_adjust'] = int.from_bytes(self._io.read(2), "little", signed=True)

                run_data.append(window_data)

            self.run_info[krun].data = run_data

        return self.run_info[krun].data


    def read_file(self):
        # Read the file header
        self.read_file_header();

        # Iterate over runs. The data get stored in self.run_info
        for krun in range(0, self.nruns):
            # Read the run header
            self.read_run_header(krun)

            # Read the run data
            self.read_run_data(krun)

        # Close the file
        self.close()


    def verify(self):
        all_checks_passed = True

        verifications = {}

        # Check whether there is, in fact, data for all runs
        if not self.all_run_data_present:
            print('WARNING: Missing data for one or more runs ...')
            verifications['all_run_data_present'] = False
            all_checks_passed = False

        if not self.all_runs_valid:
            verifications['all_runs_valid'] = False
            all_checks_passed = False

        return verifications

    @property
    def all_run_data_present(self):
        self._all_run_data_present = True

        if any(not run.data for run in self.run_info):
            self._all_run_data_present = False

        return self._all_run_data_present


    @property
    def all_runs_valid(self):
        self._all_runs_valid = True

        for run in self.run_info:
            try:
                run.verify_metronome_values()
            except:
                self._all_runs_valid = False
                continue

        return self._all_runs_valid
    

class GEMRun:
    hdr = {}
    data = []
    df = None

    def __init__(self, parent):
        self.parent = parent

    def get_data_frame(self):
        if not self.df:
            self.df = pd.DataFrame(self.data)

        return self.df

    # Method to make sure that all of the metronome values check out
    def verify_metronome_values(self):
        msec_per_tick = 1/self.hdr['tempo']*60*1000

        print(f'Verifying metronome times for run {self.hdr["run_number"]} ...')

        for idx, window in enumerate(self.data):
            curr_met_time = window['met_time']

            if expected_next_met_time and expected_next_met_time != curr_met_time:

                time_difference = curr_met_time - expected_next_met_time
                raise ValueError(f'Window f{idx}: Difference in current and expected metronome times: {time_difference}')

            expected_next_met_time = curr_met_time + msec_per_tick + window['next_met_adjust']


    # Determine whether any participants had a false start
    def false_start(self, num_pacing_clicks=2):
        df = self.get_data_frame()

        false_start = df.iloc[range(0, num_pacing_clicks)]['asynchronies'].map(lambda asynchs: any(asynch!=-32000 for asynch in asynchs)).any()

        return false_start


    # Get the indices of valid tappers
    def get_valid_tapper_idxs(self):
        return [subject['pad']-1 for subject in self.parent.file_hdr['subject_info']]


    # Calculate various statistics
    def compute_stats(self):
        valid_tappers = self.get_valid_tapper_idxs()

        df = self.get_data_frame()


