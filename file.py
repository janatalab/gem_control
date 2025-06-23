# file.py

GEM_MAX_TAPPERS = 4 # should match value specified in GEM/GEMConstants.h
MISSING_DATA_VALUE = -32000

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

        # Verify the data
        clean, verifications = self.verify()
        if not clean:
            print(f"Found problems in {self.filepath}")
            print(verifications)


    def open(self):
        mode = 'rb'
        if not self.is_open:
            if isinstance(self.filepath, storages.backends.s3.S3File):
                self._io = self.filepath.open(mode)
            else:
                self._io = open(self.filepath, mode)

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

        return all_checks_passed, verifications


    def get_missing_runs(self):
        if not hasattr(self, "_missing_runs"):
            self._missing_runs = []

            for idx, run in enumerate(self.run_info):
                if not run.hdr:
                    self._missing_runs.append(idx+1)

        return self._missing_runs


    def get_invalid_runs(self):
        if not hasattr(self, "_invalid_runs"):
            self._invalid_runs = []

            for idx, run in enumerate(self.run_info):
                try:
                    run.verify_metronome_values()

                except:
                    self._invalid_runs.append(run)
                    continue

        return self._invalid_runs         


    @property
    def all_run_data_present(self):
        if not hasattr(self, "_all_run_data_present"):
            self._all_run_data_present = False

            if not self.get_missing_runs():
                self._all_run_data_present = True

        return self._all_run_data_present


    @property
    def all_runs_valid(self):
        if not hasattr(self, "_all_runs_valid"):
            self._all_runs_valid = False 
            if not self.get_invalid_runs():
                self._all_runs_valid = True 

        return self._all_runs_valid
    

class GEMRun:

    def __init__(self, parent):
        self.parent = parent

        self.hdr = {}
        self.data = []
        self.tapper_stats = {}
        self.metronome_stats = {}
        self.group_stats = {}
        self._df = pd.DataFrame()

        # Create a dataframe 
        self.get_data_frame()

    def __repr__(self):
        return json.dumps(self.hdr)

    def get_data_frame(self):
        if self._df.empty:
            self._df = pd.DataFrame(self.data)

        return self._df

    # Method to make sure that all of the metronome values check out
    def verify_metronome_values(self):
        msec_per_tick = 1/self.hdr['tempo']*60*1000
        expected_next_met_time = None

        print(f'Verifying metronome times for run {self.hdr["run_number"]} ...')

        for idx, window in enumerate(self.data):
            curr_met_time = window['met_time']

            if expected_next_met_time and expected_next_met_time != curr_met_time:

                time_difference = curr_met_time - expected_next_met_time
                raise ValueError(f'Window {idx+1}: Difference in current and expected metronome times: {time_difference}')

            expected_next_met_time = curr_met_time + msec_per_tick + window['next_met_adjust']


    # Determine whether any participants had a false start
    def false_start(self, num_pacing_clicks=2):
        df = self.get_data_frame()

        false_start = df.iloc[range(0, num_pacing_clicks)]['asynchronies'].map(lambda asynchs: any(asynch != MISSING_DATA_VALUE for asynch in asynchs)).any()

        return false_start


    # Get the indices of valid tappers
    def get_valid_tapper_idxs(self):
        return [int(subject['pad'])-1 for subject in self.parent.file_hdr['subject_info']]


    def get_valid_tapper_ids(self):
        return [subject['id'] for subject in self.parent.file_hdr['subject_info']]


    # Calculate various statistics
    def compute_stats(self, **kwargs):
        if self in self.parent._invalid_runs:
            print(f"Run {self.hdr['run_number']} is invalid. Skipping ...")
            return

        # Get our tappers
        valid_tapper_idxs = self.get_valid_tapper_idxs()

        # Get our data frame
        df = self.get_data_frame()

        # Replace our missing data tag (-32000) with NaN
        asynchrony_data = df['asynchronies'].apply(replace_missing)

        # Convert asynchrony data to a DataFrame
        asynchrony_data = pd.DataFrame(dict(zip(asynchrony_data.index, asynchrony_data.values))).T

        # Extract the data for the tappers we actually have
        asynchrony_data = asynchrony_data.iloc[:, valid_tapper_idxs]

        # Label the columns. Note that the order will appropriately match the order in which the data were extracted using valid_tapper_idxs
        valid_tapper_ids = self.get_valid_tapper_ids()
        asynchrony_data.columns = valid_tapper_ids

        #
        # Calculate per-window statistics
        #

        # Calculate the mean tapper asynchrony for each window
        df['mean_tapper_asynchrony'] = asynchrony_data.mean(axis=1, skipna=True)

        # Calculate the std of the tapper asynchronies for each window
        df['std_tapper_asynchrony'] = asynchrony_data.std(axis=1, skipna=True)

        # Calculate tapper asynchronies relative to the group mean asynchrony
        asynchrony_rel_group = asynchrony_data.subtract(df['mean_tapper_asynchrony'], axis=0)


        # Remove data associated with pacing clicks, so as to exclude this from the per-run statistics

        # Get our number of pacing metronome tones
        num_pacing_clicks = kwargs.get('num_pacing_clicks', 0)

        asynchrony_data = asynchrony_data.iloc[num_pacing_clicks:,:]

        asynchrony_rel_group = asynchrony_rel_group.iloc[num_pacing_clicks:,:]

        #
        # Calculate per-run statistics
        # 

        per_run_subject_stats = pd.DataFrame()
        per_run_met_stats = {}
        per_run_group_stats = {}

        # Get the number of missed taps for each tapper
        per_run_subject_stats['num_missed'] = asynchrony_data.isna().sum()

        # Calculate each tapper's mean asynchrony relative to the metronome
        per_run_subject_stats['mean_async_rel_met'] = asynchrony_data.mean(skipna=True)

        # Calculate each tapper's std of the asynchronies relative to the metronome
        per_run_subject_stats['std_async_rel_met'] = asynchrony_data.std(skipna=True)

        # Calculate each tapper's mean asynchrony relative to the group average
        per_run_subject_stats['mean_async_rel_grp'] = asynchrony_rel_group.mean(skipna=True)

        # Calculate each tapper's std of the asynchronies relative to the group average
        per_run_subject_stats['std_async_rel_grp'] = asynchrony_rel_group.std(skipna=True)

        # Calculate the mean metronome adjustment
        per_run_met_stats['met_adjust_mean'] = df.loc[num_pacing_clicks:,'next_met_adjust'].mean()

        # Calculate the std of metronome adjustments
        per_run_met_stats['met_adjust_std'] = df.loc[num_pacing_clicks:,'next_met_adjust'].std()

        # Calculate the mean of the per-window group mean asynch
        per_run_group_stats['mean_grp_mean_asynch_per_window'] = df['mean_tapper_asynchrony'].mean(skipna=True)

        # Calculate the std of the per-window group mean asynch
        per_run_group_stats['std_grp_mean_asynch_per_window'] = df['mean_tapper_asynchrony'].std(skipna=True)

        # Calculate the mean of the per-window group sd asynch
        per_run_group_stats['mean_grp_std_asynch_per_window'] = df['std_tapper_asynchrony'].mean(skipna=True)

        # Calculate the std of the per-window group sd asynch
        per_run_group_stats['std_grp_std_asynch_per_window'] = df['std_tapper_asynchrony'].std(skipna=True)

        # Update our stats
        self.tapper_stats.update(per_run_subject_stats.T.to_dict())
        self.metronome_stats.update(per_run_met_stats)
        self.group_stats.update(per_run_group_stats)

        return


def replace_missing(values):
    return [v if v > MISSING_DATA_VALUE else pd.NA for v in values]
