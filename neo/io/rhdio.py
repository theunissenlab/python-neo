# -*- coding: utf-8 -*-
"""
Class for "reading" data from Intan RHD files.
Depends on: intanutil
Supported: Read
Author: theunissen lab
"""

# needed for python 3 compatibility
from __future__ import absolute_import
import numpy as np
import quantities as pq
from neo.io.baseio import BaseIO
from neo.core import Block, Segment, AnalogSignal, Event, ChannelIndex
from intanutil import load_intan_rhd_format, read_header

from os.path import basename


class RHDIO(BaseIO):

    is_readable = True  # This class can only read data
    is_writable = False  # write is not supported

    # This class is able to directly or indirectly handle the following objects
    # You can notice that this greatly simplifies the full Neo object hierarchy
    supported_objects = [Segment, AnalogSignal]

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
        Segment: [
            ('segment_duration',
                {'value': 15., 'label': 'Segment size (s.)'}),
            ('num_analogsignal',
                {'value': 8, 'label': 'Number of recording points'}),
            ('num_spiketrain_by_channel',
                {'value': 3, 'label': 'Num of spiketrains'}),
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

    def read_segment(self,
                     lazy=False,
                     cascade=True,
                     block=None,
                     storeDIG=True,
                     **kwargs):
        """
        Return an RHD segment loaded from self.filename.
        TODO: Is recording time a default component of the filename?
        TODO: Should channels be native_order or custom_order?
        """

        # Create a segment
        segment = Segment(name=basename(self.filename), file_origin=self.filename)

        # Read the header to get segment metadata
        with open(self.filename, "rb") as fid:
            header = read_header.read_header(fid)

        # Annotate with all frequency_parameter keys that do not end in sample_rate
        segment_annotations = dict((key, val) for key, val
                                   in header["frequency_parameters"].items()
                                   if not key.endswith("sample_rate"))

        # Also add all of notes
        for note_name, note in header["notes"].items():
            segment_annotations[note_name] = note

        segment.annotate(**segment_annotations)

        if cascade is False:
            return segment

        if lazy is False:
            try:
                data = load_intan_rhd_format.read_data(self.filename, parallelFlg=True)
            except load_intan_rhd_format.RHDError:
                print("Error! The file may be corrupted!")
                raise

        # Create analog signals
        # First start with amplifier data which comes from the Intan chip
        if lazy is False:
            signals = data.pop("amplifier_data").T
        else:
            signals = np.array([])

        channels = [ch["native_order"] for ch in header["amplifier_channels"]]
        channel_names = [ch["native_channel_name"] for ch in
                         header["amplifier_channels"]]
        sampling_rate = header["frequency_parameters"]["amplifier_sample_rate"]
        channel_idx = ChannelIndex(name='Amplifier', index=channels,
                                   channel_names=channel_names,
                                   channel_details=header["amplifier_channels"])
        signals = AnalogSignal(signals,
                               name="Amplifier",
                               units=pq.microvolt,
                               t_start=0*pq.s,
                               sampling_rate=sampling_rate*pq.Hz,
                               file_origin=self.filename,
                               copy=False)
        channel_idx.analogsignals.append(signals)
        segment.analogsignals.append(signals)
        block.channel_indexes.append(channel_idx)
        block.create_many_to_one_relationship(force=True, recursive=True)
        block.create_many_to_many_relationship()

        # Now get ADC channel data. This is additonal analog inputs to the Intan board
        if header["num_board_adc_channels"] > 0:
            if lazy is False:
                signals = data.pop("board_adc_data").T
            else:
                signals = np.array([])
            channels = [ch["native_order"] for ch in header["board_adc_channels"]]
            channel_names = [ch["native_channel_name"] for ch in
                             header["board_adc_channels"]]
            sampling_rate = header["frequency_parameters"]["board_adc_sample_rate"]
            channel_idx = ChannelIndex(name='ADC', index=channels,
                                       channel_names=channel_names,
                                       channel_details=header["board_adc_channels"])
            signals = AnalogSignal(signals,
                                   name="Board ADC",
                                   units=pq.volt,
                                   t_start=0*pq.s,
                                   sampling_rate=sampling_rate*pq.Hz,
                                   file_origin=self.filename,
                                   copy=False)
            channel_idx.analogsignals.append(signals)
            segment.analogsignals.append(signals)
            block.channel_indexes.append(channel_idx)
            block.create_many_to_one_relationship(force=True, recursive=True)
            block.create_many_to_many_relationship()

        # Import aux data
        if header["num_aux_input_channels"] > 0:
            if lazy is False:
                signals = data.pop("aux_input_data").T
            else:
                signals = np.array([])
            channels = [ch["native_order"] for ch in header["aux_input_channels"]]
            channel_names = [ch["native_channel_name"] for ch in
                             header["aux_input_channels"]]
            sampling_rate = header["frequency_parameters"]["aux_input_sample_rate"]
            channel_idx = ChannelIndex(name='AuxData', index=channels,
                                       channel_names=channel_names,
                                       channel_details=header["aux_input_channels"])
            signals = AnalogSignal(signals,
                                   name="AUX Input",
                                   units=pq.volt,
                                   t_start=0*pq.s,
                                   sampling_rate=sampling_rate*pq.Hz,
                                   file_origin=self.filename,
                                   copy=False)
            channel_idx.analogsignals.append(signals)
            segment.analogsignals.append(signals)
            block.channel_indexes.append(channel_idx)
            block.create_many_to_one_relationship(force=True, recursive=True)
            block.create_many_to_many_relationship()

        # Create event arrays from digital inputs
        # Loop through all rows of the digital input data and create event arrays
        if (header["num_board_dig_in_channels"]) > 0:
            if storeDIG:
                sampling_rate = data["frequency_parameters"]["board_dig_in_sample_rate"]
                # channel = header["board_dig_in_channels"][ii]["native_order"]
                channels = [ch["native_order"] for ch in header["board_dig_in_channels"]]
                channel_names = [ch["native_channel_name"] for ch in
                             header["board_dig_in_channels"]]
                channel_idx = ChannelIndex(name='EventData', index=channels,
                                       channel_names=channel_names,
                                       channel_details=header["board_dig_in_channels"])
                for ii, digital_signal in enumerate(data["board_dig_in_data"]):
                    times = np.nonzero(digital_signal)[0] / sampling_rate
                    if len(times) < 1:
                        continue
                    channel = header["board_dig_in_channels"][ii]["native_order"]
                    ea = Event(times=times*pq.s,
                           name="Digital Input Events {}".format(channel),
                           channel_ids=channels[ii],
                           channel_names=channel_names[ii],
                           file_origin=self.filename,
                        #    channel_details=header["board_dig_in_channels"][ii],
                           sampling_rate=sampling_rate*pq.Hz)
                    #channel_idx.events.append(ea)
                    segment.events.append(ea)
                block.channel_indexes.append(channel_idx)
                block.create_many_to_one_relationship(force=True, recursive=True)
                block.create_many_to_many_relationship()
                segment.create_many_to_one_relationship()
            else:
                print(header["num_board_dig_in_channels"],' found in rhd file but will NOT be stored')

        del data

        return segment

    def read_block(self, lazy=False, cascade=True, storeDIG=True, **kwargs):
        bl = Block(name=basename(self.filename), file_origin=self.filename)
        segment = self.read_segment(lazy=lazy, cascade=cascade, block=bl, storeDIG=storeDIG, **kwargs)

        bl.segments.append(segment)
        bl.create_many_to_one_relationship()

        return bl
