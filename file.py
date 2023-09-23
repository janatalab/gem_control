# file.py

GEM_MAX_TAPPERS = 4 # should match value specified in GEM/GEMConstants.h

# GEMDataFile is copied from GEM/GUI/GEMIO.py
class GEMDataFile:
    def __init__(self, filepath, nrun, mode="wb+"):
        self.filepath = filepath

        self._io = open(filepath, mode)
        self.is_open = True
        self.ptr = 0

        self.file_hdr = {}

        # position in the file of the start of the run header offset list
        self.idx_map_offset = 0

        # list start and end offsets for each run
        self.run_offsets = [-1] * nrun

        self.current_run = 0

    def close(self):
        if self.is_open:
            self.ptr = self._io.tell()
            self._io.close()
            self._io = None
            self.is_open = False

    def reopen(self):
        if not self.is_open:
            self._io = open(self.filepath, "r+b")
            self._io.seek(self.ptr, 0)
            self.is_open = True

    def write_header(self, krun, hdr_dict):
        self.reopen()
        if krun >= 0:
            if krun >= len(self.run_offsets):
                raise ValueError("\"%d\" is not a valid run number!" % krun)

            if self.run_offsets[krun] < 0:
                self.run_offsets[krun] = self._io.tell()
                self.write_run_offset(krun, self.run_offsets[krun])

            else:
                # the current run <krun> was previously aborted, so seek back
                # to where that run started to overwrite that run's data
                self._io.seek(self.run_offsets[krun], 0)

        hdr_str = json.dumps(hdr_dict)
        nel = len(hdr_str)
        nel_uint64 = uint64(nel)

        # Write the length of the header dict as an 8 byte unsigned int
        self._io.write(nel_uint64) 

        # Write the header
        hdr_offset = self._io.tell()
        print(f"Writing header of length {nel} ({nel_uint64}) at {hdr_offset}: \n{hdr_str}")
        self._io.write(hdr_str.encode())

    def write_file_header(self, d, nruns):
        self.reopen()
        self._io.seek(0, 0)
        self.write_header(-1, d)

        # initialize a block of run_header offsets with 64bit 0s
        self.idx_map_offset = self._io.tell()
        print("Writing idx_map @ {}".format(self.idx_map_offset))
        
        self._io.write(bytes(8*nruns))

    def write_run_offset(self, krun, offset):
        self.reopen()
        ptr = self._io.tell()
        print("Writing run {} offset ({}) at: {}".format(krun+1, offset, self.idx_map_offset + (krun * 8)))
        self._io.seek(self.idx_map_offset + (krun * 8), 0)
        self._io.write(uint64(offset))
        self._io.seek(ptr, 0)

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

        # Determine the number of runs
        if "nruns" not in self.file_hdr.keys():
            self.nruns = len(self.file_hdr["metronome_alpha"])*len(self.file_hdr["metronome_tempo"])*self.file_hdr["repeats"]

        # Read the run offset information
        self.idx_map_offset = self._io.tell()

        self.run_offsets = []
        self.run_info = []

        for r in range(0, self.nruns):
            self.run_offsets.append(int.from_bytes(self._io.read(8), "little"))
            self.run_info.append({})


    def read_run_header(self, krun):
        # Read the file header and run offsets if we haven't yet
        if not self.run_offsets:
            self.read_file_header()

        offset = self.run_offsets[krun]
        hdr_dict = self.read_header(offset)

        self.run_info[krun]['hdr'] = hdr_dict

        return hdr_dict

    def read_run_data(self, krun):
        run_data = []

        # Seek to the start of the run
        self._io.seek(self.run_offsets[krun], 0)

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

        self.run_info[krun]['data'] = run_data

        return run_data

    def read_file(self):
        # Read the file header
        self.read_file_header();

        # Iterate over runs
        for krun in range(0, self.nruns):
            # Read the run header
            self.read_run_header(krun)

            # Read the run data
            self.read_run_data(krun)

        # Close the file
        self.close()
