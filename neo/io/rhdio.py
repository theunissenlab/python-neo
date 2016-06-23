# -*- coding: utf-8 -*-
"""
Class for "reading" data from Intan RHD files.

Depends on: intanutil

Supported: Read

Author: theunissen lab
"""

# needed for python 3 compatibility
from __future__ import absolute_import

# note neo.core needs only numpy and quantities
import numpy as np
import quantities as pq

# I need to subclass BaseIO
from neo.io.baseio import BaseIO

# to import from core
from neo.core import Segment, AnalogSignalArray, SpikeTrain, EventArray, RecordingChannelGroup
from intanutil import load_intan_rhd_format, read_header

def convert_digital_to_metadata(signal, code_length=384, bits_per_char=8):
    dig_on = np.nonzero(signal)[0]
    gaps = np.hstack([np.array(np.inf), np.diff(dig_on)])
    starts = dig_on[gaps > code_length]
    codes = list()
    for start in starts:
        code = binary_converter(signal[start + 1: start + 1 + code_length], bits_per_char)
        codes.append((start, code))

    return codes

def binary_converter(code, bits_per_char):
    num_vals = len(code) / bits_per_char
    vals = np.zeros(num_vals)
    for ii in range(num_vals):
        binvec = code[ii * bits_per_char: (ii + 1) * bits_per_char]
        vals[ii] = np.sum((2 ** np.arange(bits_per_char - 1, -1, -1)) * binvec)

    return map(chr, vals.astype(np.int8))


class RHDIO(BaseIO):

    is_readable = True  # This class can only read data
    is_writable = False  # write is not supported

    # This class is able to directly or indirectly handle the following objects
    # You can notice that this greatly simplifies the full Neo object hierarchy
    supported_objects = [Segment, AnalogSignalArray]

    # This class can return either a Block or a Segment
    # The first one is the default ( self.read )
    # These lists should go from highest object to lowest object because
    # common_io_test assumes it.
    readable_objects = [Segment]
    # This class is not able to write objects
    writeable_objects = []

    has_header = False
    is_streameable = False

    # This is for GUI stuff : a definition for parameters when reading.
    # This dict should be keyed by object (`Block`). Each entry is a list
    # of tuple. The first entry in each tuple is the parameter name. The
    # second entry is a dict with keys 'value' (for default value),
    # and 'label' (for a descriptive name).
    # Note that if the highest-level object requires parameters,
    # common_io_test will be skipped.
    read_params = {
        Segment : [
            ('segment_duration',
                {'value' : 15., 'label' : 'Segment size (s.)'}),
            ('num_analogsignal',
                {'value' : 8, 'label' : 'Number of recording points'}),
            ('num_spiketrain_by_channel',
                {'value' : 3, 'label' : 'Num of spiketrains'}),
            ],
        }

    # do not supported write so no GUI stuff
    write_params = None

    name = 'RHD'

    extensions = ['rhd']

    # mode can be 'file' or 'dir' or 'fake' or 'database'
    # the main case is 'file' but some reader are base on a directory or a database
    # this info is for GUI stuff also
    mode = 'file'

    def __init__(self, filename=None):
        """
        Arguments:
            filename : the filename
        """

        BaseIO.__init__(self)
        self.filename = filename
        # Seed so all instances can return the same values
        np.random.seed(1234)

    # Segment reading is supported so I define this :
    def read_segment(self,
                     lazy=False,
                     cascade=True,
                     **kwargs):
        """
        Return an RHD segment loaded from self.filename.

        TODO:
        - Is recording time a default component of the filename?
        - Add channel data as annotations somewhere
        - Placeholder for spike triggers (Can this be used to import spiketrains?)
        - Import aux input data as analog signals?
        - What to do about digital output channels?
        - How to handle channels that don't exist?
        - Add lazy loading
        - Add logging
        """

        # Create a segment
        segment = Segment(name=self.filename, file_origin=self.filename)

        # Read the header to get segment metadata
        with open(self.filename, "rb") as fid:
            header = read_header.read_header(fid)

        # Annotate with all frequency_parameter keys that do not end in sample_rate
        segment_annotations = dict([(key, val) for key, val in header["frequency_parameters"] if not key.endswith("sample_rate")])

        # Also add all of notes
        for note_name, note in header["notes"]:
            segment_annotations[note_name] = note

        segment.annotate(**segment_annotations)

        if cascade is False:
            return segment

        if lazy is False:
            data = load_intan_rhd_format.read_data(self.filename)

        # Create analog signals
        # First start with amplifier data which comes from the Intan chip
        amplifier_data = data.pop("amplifier_data").T.copy()
        amplifier_signals = AnalogSignalArray(amplifier_data,
                                              name="Amplifier",
                                              units=pq.microvolt,
                                              t_start=0*pq.s,
                                              sampling_rate=data["frequency_parameters"]["amplifier_sample_rate"]*pq.Hz,
                                              channel_index=data.pop("amplifier_channels"),
                                              file_origin=self.filename)
        segment.analogsignalarrays.append(amplifier_signals)

        # Now get ADC channel data. This is additonal analog inputs to the Intan board
        adc_data = data.pop("board_adc_data").T.copy()
        adc_signals = AnalogSignalArray(adc_data,
                                        name="Board ADC",
                                        units=pq.volt,
                                        t_start=0*pq.s,
                                        sampling_rate=data["frequency_parameters"]["board_adc_sample_rate"]*pq.Hz,
                                        channel_index=data.pop("board_adc_channels"),
                                        file_origin=self.filename)
        segment.analogsignalarrays.append(adc_signals)

        # Import aux data
        aux_data = data.pop("aux_input_data").T.copy()
        aux_signals = AnalogSignalArray(aux_data,
                                        name="AUX Input",
                                        units=pq.volt,
                                        t_start=0*pq.s,
                                        sampling_rate=data["frequency_parameters"]["aux_input_sample_rate"]*pq.Hz,
                                        channel_index=data.pop("aux_input_channels"),
                                        file_origin=self.filename)
        segment.analogsignalarrays.append(aux_signals)

        # Create event arrays from digital inputs
        # Loop through all rows of the digital input data and create event arrays
        for ii in range(data["board_dig_in_data"])
        segment.create_many_to_one_relationship()

        return segment

    def read_block(self, lazy=False, cascade=True, **kwargs):

        bl = Block(name=self.filename, file_origin=self.filename)
        segment = self.read_segment(lazy=lazy, cascade=cascade, **kwargs)

        # Create a RecordingChannelGroup for each AnalogSignalArray
        for asigarray in segment.analogsignalarrays:
            rcg = RecordingChannelGroup(name=)
        bl.segments.append(segment)


        bl.create_many_to_one_relationship()

        return bl
