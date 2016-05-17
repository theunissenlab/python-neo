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
from neo.core import Segment, AnalogSignalArray, SpikeTrain, EventArray
from intanutil import load_intan_rhd_format as rhd

class RHDIO(BaseIO):

    is_readable = True # This class can only read data
    is_writable = False # write is not supported

    # This class is able to directly or indirectly handle the following objects
    # You can notice that this greatly simplifies the full Neo object hierarchy
    supported_objects  = [ Segment , AnalogSignal, SpikeTrain, EventArray ]

    # This class can return either a Block or a Segment
    # The first one is the default ( self.read )
    # These lists should go from highest object to lowest object because
    # common_io_test assumes it.
    readable_objects    = [Segment]
    # This class is not able to write objects
    writeable_objects   = [ ]

    has_header         = False
    is_streameable     = False

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
    write_params       = None

    name               = 'RHD'

    extensions          = [ 'rhd' ]

    # mode can be 'file' or 'dir' or 'fake' or 'database'
    # the main case is 'file' but some reader are base on a directory or a database
    # this info is for GUI stuff also
    mode = 'file'

    def __init__(self , filename = None) :
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
                     # the 2 first keyword arguments are imposed by neo.io API
                     lazy = False,
                     cascade = True,
                     # all following arguments are decied by this IO and are free
                     segment_duration = 15.,
                     num_analogsignal = 4,
                     num_spiketrain_by_channel = 3,
                    ):
        """
        Return an RHD segment loaded from self.filename.

        Parameters:
            segment_duration :is the size in secend of the segment.
            num_analogsignal : number of AnalogSignal in this segment
            num_spiketrain : number of SpikeTrain in this segment


        TODO:
        - Add channel data as annotations somewhere
        - Placeholder for supply voltage (what is this?? Import as analog signal?)
        - Placeholder for spike triggers (Can this be used to import spiketrains?)
        - Notes as segment annotations
        - Frequency parameters, annotate segment with other keys
        - Import aux input data as analog signals?
        - What to do about digital output channels?
        - How to handle channels that don't exist?
        - Add lazy loading
        - Add cascade something or other
        - Add logging
        """

        data = rhd.read_data(self.filename)

        # Create a segment
        # TODO: Parse filename for recording time
        # TODO: Add data["notes"] as annotations on the segment
        segment = Segment(name=self.filename, file_origin=self.filename)

        # Create analog signals
        # First start with amplifier data
        amplifier_signals = AnalogSignalArray(data["amplifier_data"].T,
                                              name="Amplifier",
                                              units=pq.microvolt,
                                              t_start=0*pq.s,
                                              sampling_rate=data["frequency_parameters"]["amplifier_sample_rate"]*pq.Hz)
        segment.analogsignalarrays.append(amplifier_signals)

        # Now get ADC channel data
        # TODO: Is this in volt or millivolt?
        # In each dictionary is a lot of useful information about the channel.
        adc_signals = AnalogSignalArray(data["board_adc_data"].T,
                                        name="Board ADC",
                                        units=pq.millivolt,
                                        t_start=0*pq.s,
                                        sampling_rate=data["frequency_parameters"]["board_adc_sample_rate"]*pq.Hz)
        segment.analogsignalarrays.append(adc_signals)

        # Import aux data
        # TODO: Is this in volt or millivolt?
        aux_signals = AnalogSignalArray(data["aux_input_data"].T,
                                        name="AUX Input",
                                        units=pq.volt,
                                        t_start=0*pq.s,
                                        sampling_rate=data["frequency_parameters"]["aux_input_sample_rate"]*pq.Hz)

        segment.analogsignalarrays.append(aux_signals)
        # Create event arrays from digital inputs
        # Loop through all rows of the digital input data and create event arrays

        segment.create_many_to_one_relationship()

        return segment
