#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
# logging.basicConfig has to be before astm import, otherwise logs don't appear
logging.basicConfig(format='%(asctime)s %(levelname)s [%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
# Log Level:
# CRITICAL
# ERROR
# WARNING
# INFO
# DEBUG

import driver.cnl24lib as cnl24lib
import binascii

import pickle # needed for local history export

if __name__ == '__main__':

    with open('history_data.dat', 'rb') as input_file:
        history_pages = pickle.load(input_file)

    mt = cnl24lib.Medtronic600SeriesDriver()
    events = mt.process_pump_history(history_pages, cnl24lib.HistoryDataType.PUMP_DATA)
    print ("# All events:")
    for ev in events:
        # if ev.event_type == cnl24lib.NGPHistoryEvent.EVENT_TYPE.REWIND: # or ev.event_type == cnl24lib.NGPHistoryEvent.EVENT_TYPE.TIME_RESET:
        # if ev.event_type == cnl24lib.NGPHistoryEvent.EVENT_TYPE.ALARM_CLEARED and "Don't parse data" in ev.alarm_string :
        #     print (ev, binascii.hexlify(ev.eventData) )

        if ev.event_type != cnl24lib.NGPHistoryEvent.EVENT_TYPE.PLGM_CONTROLLER_STATE:
            print (ev )

    print ("# End events")

    # ii = 0
    # for i in range(len(self.eventData)):
    #     if i >= 0x0B:
    #         ii = i - 0x0B
    #         print("0x{0:X} + (0x0B+0x{2:X}) -> 0x{1:X}".format(i, BinaryDataDecoder.read_byte(self.eventData, i), ii))
    #     else:
    #         print("0x{0:X} + (0x0B+0x{2:X}) -> 0x{1:X}".format(i, BinaryDataDecoder.read_byte(self.eventData, i), ii))