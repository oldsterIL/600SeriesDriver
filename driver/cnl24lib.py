#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
# logging.basicConfig has to be before astm import, otherwise logs don't appear
logging.basicConfig(format='%(asctime)s %(levelname)s [%(name)s] %(message)s', level=logging.WARNING)
logger = logging.getLogger(__name__)

import hid
import binascii
import struct
import astm
import re
import hashlib
import sqlite3
import crc16
import Crypto.Cipher.AES
import datetime
from dateutil import tz
import lzo
from datetime import timedelta

VERSION = "0.1"

# MEAL_WIZARD_ESTIMATE
# CLOSED_LOOP_TRANSITION
# CLOSED_LOOP_DAILY_TOTALS
# CLOSED_LOOP_ALARM_AUTO_CLEARED
# ClosedLoopBloodGlucoseReadingEvent CLOSED_LOOP_BG_READING

# BOLUS_SUSPENDED:
# 0199020000c35000000cb2
# NGPHistoryEvent 0xD4 OLD_HIGH_SENSOR_WARNING_LEVELS - No parsed
# NGPHistoryEvent 0xD5 NEW_HIGH_SENSOR_WARNING_LEVELS - No parsed
# PLGMControllerStateEvent - No parsed
# SENSOR_GLUCOSE_GAP 0xCD - No parsed



################# HISTORY ######################
class NGPConstants:

    class BG_UNITS:
        MG_DL = 0
        MMOL_L = 1
        MMOLXLFACTOR = 18.016

    BG_UNITS_NAME = {
        0: "Mg\dl",
        1: "Mmol\l"
    }

    class CARB_UNITS:
        GRAMS = 0
        EXCHANGES = 1

    CARB_UNITS_NAME = {
        0: "Grams",
        1: "Exchanges"
    }

    class BG_SOURCE:
        EXTERNAL_METER = 1
        BOLUS_WIZARD = 2,
        BG_EVENT_MARKER = 3
        SENSOR_CAL = 4

    BG_SOURCE_NAME = {
        1: "External meter",
        2: "Bolus wizard",
        3: "BG event marker",
        4: "Sensor calibration",
        -1: "NA"
    }

    class BG_ORIGIN:
        MANUALLY_ENTERED = 0
        RECEIVED_FROM_RF = 1

    class BG_CONTEXT:
        BG_READING_RECEIVED = 0
        USER_ACCEPTED_REMOTE_BG = 1
        USER_REJECTED_REMOTE_BG = 2
        REMOTE_BG_ACCEPTANCE_SCREEN_TIMEOUT = 3
        BG_SI_PASS_RESULT_RECD_FRM_GST = 4
        BG_SI_FAIL_RESULT_RECD_FRM_GST = 5
        BG_SENT_FOR_CALIB = 6
        USER_REJECTED_SENSOR_CALIB = 7
        ENTERED_IN_BG_ENTRY = 8
        ENTERED_IN_MEAL_WIZARD = 9
        ENTERED_IN_BOLUS_WIZRD = 10
        ENTERED_IN_SENSOR_CALIB = 11
        ENTERED_AS_BG_MARKER = 12

    class BOLUS_SOURCE:
        MANUAL = 0
        BOLUS_WIZARD = 1
        EASY_BOLUS = 2
        PRESET_BOLUS = 4
        CLOSED_LOOP_MICRO_BOLUS = 5
        CLOSED_LOOP_BG_CORRECTION = 6
        CLOSED_LOOP_FOOD_BOLUS = 7
        CLOSED_LOOP_BG_CORRECTION_AND_FOOD_BOLUS = 8
        NA = -1

    BOLUS_SOURCE_NAME = {
        0: "Manual",
        1: "Bolus wizard",
        2: "Easy bolus",
        4: "Preset bolus",
        5: "Closed loop micro bolus",
        6: "Closed loop BG correction",
        7: "Closed loop food bolus",
        8: "Closed loop BG correction and food bolus",
        -1: "NA",
    }

    CANNULA_FILL_TYPE ={
        0: "Tubing fill",
        1: "Cannula fill"
    }


    class BOLUS_STEP_SIZE:
        STEP_0_POINT_025 = 0
        STEP_0_POINT_05 = 1
        STEP_0_POINT_1 = 2

    BOLUS_STEP_SIZE_NAME = {
        0: "Step 0.025",
        1: "Step 0.05",
        2: "Step 0.1",
       -1: "NA"
    }
    SENSOR_EXCEPTIONS_NAME = {
        0x0000: "Lost connection to sensor",
        0x0300: "Sensor OK",
        0x0301: "Sensor warming up",
        0x0302: "Calibrate sensor now",
        0x0303: "Updating sensor",
        0x0304: "Calibration error",
        0x0305: "Change sensor",
        0x0306: "Sensor expired",
        0x0307: "Sensor not ready",
        0x0308: "Sensor reading too high",
        0x0309: "Sensor reading too low",
        0x030A: "Calibrating sensor",
        0x030B: "Calibrating error - Change sensor",
        0x030C: "Time unknown",
    }

    BASAL_PATTERN_NAME = {
        1: "Pattern 1",
        2: "Pattern 2",
        3: "Pattern 3",
        4: "Pattern 4",
        5: "Pattern 5",
        6: "Workday",
        7: "Day Off",
        8: "Sick Day"
    }

    class TEMP_BASAL_TYPE:
        ABSOLUTE = 0
        PERCENT = 1

    TEMP_BASAL_TYPE_NAME = {
        0: "Insulin units",
        1: "Percentage"
    }

    class DUAL_BOLUS_PART:
        NORMAL_BOLUS = 1
        SQUARE_WAVE = 2
        DUAL_WAVE = 5

    DUAL_BOLUS_PART_NAME = {
        0: "Off",
        1: "Normal bolus",
        2: "Square wave",
        5: "Dual wave"
    }

    TEMP_BASAL_PRESET_NAME = {
        0: "Manual",
        1: "Temp 1",
        2: "Temp 2",
        3: "Temp 3",
        4: "Temp 4",
        5: "High Activity",
        6: "Moderate Activity",
        7: "Low Activity",
        8: "Sick",
    }

    BOLUS_PRESET_NAME = {
        0: "Manual",
        1: "Bolus 1",
        2: "Bolus 2",
        3: "Bolus 3",
        4: "Bolus 4",
        5: "Breakfast",
        6: "Lunch",
        7: "Dinner",
        8: "Snack",
        49: "NA"
    }

    class SUSPEND_REASON:
        ALARM_SUSPEND = 1  # Battery change, cleared occlusion, etc
        USER_SUSPEND = 2
        AUTO_SUSPEND = 3
        LOWSG_SUSPEND = 4
        SET_CHANGE_SUSPEND = 5  # AKA NOTSEATED_SUSPEND
        PLGM_PREDICTED_LOW_SG = 10

    SUSPEND_REASON_NAME = {
        1: 'Alarm suspend',
        2: 'User suspend',
        3: 'Auto suspend',
        4: 'Low glucose suspend',
        5: 'Set change suspend',
        10: 'Predicted low glucose suspend',
    }

    class RESUME_REASON:
        USER_SELECTS_RESUME = 1
        USER_CLEARS_ALARM = 2
        LGM_MANUAL_RESUME = 3
        LGM_AUTO_RESUME_MAX_SUSP = 4  # After an auto suspend, but no CGM data afterwards.
        LGM_AUTO_RESUME_PSG_SG = 5  # When SG reaches the Preset SG level
        LGM_MANUAL_RESUME_VIA_DISABLE = 6

    RESUME_REASON_NAME = {
        1: 'User resumed',
        2: 'User cleared alarm',
        3: 'Low glucose manual resume',
        4: 'Low glucose auto resume - max suspend period',
        5: 'Low glucose auto resume - preset glucose reached',
        6: 'Low glucose manual resume via disable',
    }

    class AUDIO_MODE:
        SOUND = 0
        VIBRATION = 1
        SOUND_VIBRATION = 2

    AUDIO_MODE_NAME = {
        0: 'Sound',
        1: 'Vibration',
        2: 'Sound+Vibration',
    }

    #### Alarms ####
    class ALARM_TYPE:
        PUMP = 1
        SENSOR = 2
        REMINDER = 3
        SMARTGUARD = 4
        AUTOMODE = 5

    ALARM_TYPE_NAME = {
        1: "Pump Alert",
        2: "Sensor Alert",
        3: "Reminder",
        4: "SmartGuard",
        5: "Auto mode alert"
    }

    class ALARM_PRIORITY:
        REDUNDANT = -9
        LOWEST = -2
        LOW = -1
        NORMAL = 0
        HIGH = 1
        EMERGENCY = 2

    ALARM_PRIORITY_NAME = {
        -9: "Redundant",
        -2: "Lowest",
        -1: "Low",
         0: "Normal",
         1: "High",
         2: "Emergency",
    }

    ALARM_MESSAGE_NAME = {
        3   : "Pump error 3|Delivery stopped. Settings unchanged. Select OK to continue. See User Guide.",
        4   : "Pump error 4|Delivery stopped. Settings unchanged. Select OK to continue. See User Guide.",
        6   : "Power loss|AA battery was removed for more than 10 min or power was lost. Select OK to re-enter time and date.",
        7   : "Insulin flow blocked|Check BG. Consider injection and testing ketones. Change reservoir and infusion set.",
        8   : "Insulin flow blocked|Estimated 0U insulin in reservoir. Change reservoir and infusion set.",
        11  : "Replace battery now|Delivery stopped. Battery must be replaced to resume delivery.",
        15  : "Pump error 15|Delivery stopped. Settings unchanged. Select OK to continue. See User Guide.",
        23  : "Pump error 23|Delivery stopped. Settings unchanged. Select OK to continue. See User Guide.",
        53  : "Pump error 53|Delivery stopped. Settings unchanged. Select OK to continue. See User Guide.",
        54  : "Pump error 54|Delivery stopped. Settings unchanged. Select OK to continue. See User Guide.",
        58  : "Battery Failed|Insert a new AA battery.",
        61  : "Stuck button|Button pressed for more than 3 minutes",
        66  : "No reservoir detected|Rewind before loading reservoir.",
        70  : "Fill Cannula?|Select Fill to fill cannula or select Done if not needed.",
        71  : "Max Fill reached|{0}. Did you see drops at the end of tubing?",
        72  : "Max Fill reached|{0}. Remove reservoir and select Rewind to restart New Reservoir procedure.",
        73  : "Replace battery|Battery life less than 30 minutes. To ensure insulin delivery, replace battery now.",
        84  : "Insert Battery|Delivery stopped. Insert a new battery now.",
        100 : "Bolus Not Delivered|Bolus entry timed out before delivery. If bolus intended, enter values again.",
        104 : "Low battery Pump|Replace battery soon.",
        105 : "Low Reservoir {0} remain|Change reservoir soon.",
        106 : "Low Reservoir {0} hours remain|Change reservoir soon.",
        107 : "Missed Meal Bolus|No bolus delivered during the time set in the reminder.",
        108 : "Reminder|{0} at {1}",
        109 : "Set Change Reminder: {0} since the last set change|Time to change reservoir and infusion set.",
        110 : "Sensor alert occurred|Check Alarm History for silenced alerts.",
        113 : "Reservoir estimate at 0U|To ensure insulin delivery change reservoir.",
        117 : "Active Insulin cleared|Any Active Insulin amount has been cleared.",
        775 : "Calibrate Now|Check BG and calibrate sensor.",
        776 : "Calibration not accepted|Recheck BG and calibrate sensor.",
        777 : "Change Sensor|Sensor not working properly. Insert new sensor.",
        778 : "Change Sensor|Second calibration not accepted. Insert new sensor.",
        780 : "Lost sensor signal|Move pump closer to transmitter. May take 15 minutes to find signal.",
        781 : "Possible signal interference|Move away from electronic devices. May take 15 minutes to find signal.",
        784 : "Rise Alert|Sensor glucose rising rapidly.",
        788 : "BG not received|Place pump close to transmitter. Select OK to resend BG to transmitter.",
        790 : "Cannot find sensor signal|Disconnect and reconnect transmitter. Notice if transmitter light blinks.",
        791 : "Sensor signal not found|Did transmitter light blink when connected to sensor?",
        794 : "Sensor expired|Insert new sensor.",
        795 : "Check connection|Ensure transmitter and sensor connection is secure.",
        796 : "Sensor signal not found|See User Guide.",
        797 : "Sensor connected|Start new sensor.",
        798 : "Sensor connected|If new sensor, select Start New. If not, select Reconnect.",
        799 : "Sensor warm-up started|Warm-up takes up to 2 hours. you will be notified when calibration is needed.",
        801 : "SG value not available|If problem continues, see User Guide.",
        802 : "Alert On Low {0} ({1})|Low sensor glucose. Check BG.",
        803 : "Alert On Low while suspended|Low sensor glucose. Insulin delivery suspended. Check BG.",
        805 : "Alert Before Low {0} ({1})|Sensor glucose approaching Low Limit. Check BG.",
        806 : "Basal Delivery Resumed|(quiet)",
        807 : "Basal Delivery Resumed|Basal delivery resumed at {0} after suspend by sensor. Check BG.",
        808 : "Basal Delivery Resumed|Maximum 2 hour suspend time reached. Check BG.",
        809 : "Suspend On Low|Delivery stopped. Sensor glucose {0} ({1}). Check BG.",
        810 : "Suspend Before Low|(quiet)",
        811 : "Suspend Before Low|Delivery stopped. Sensor glucose approaching Low Limit. Check BG.",
        812 : "Suspend Before Low|Patient unresponsive, medical device emergency.",
        814 : "Basal Delivery Resumed|Maximum 2 hour suspend time reached. SG is still under Low limit. Check BG.",
        815 : "Basal Delivery Resumed|Low settings change caused basal to be resumed. Check BG.",
        816 : "Alert On High {0} ({1})|High sensor glucose. Check BG.",
        817 : "Alert Before High {0} ({1})|Sensor glucose approaching High Limit. Check BG.",
        869 : "Calibrate by {0}|Check BG and calibrate sensor to continue receiving sensor information.",
        870 : "Low Transmitter Battery|Recharge transmitter within 24 hours.",
    }

    ALARM_PERSONAL_REMINDER = "Personal 1|Personal 2|Personal 3|Personal 4|Personal 5|Personal 6|BG Check|Medication"
    ALARM_MISSED_MEAL_BOLUS_REMINDER = "Meal 1|Meal 2|Meal 3|Meal 4|Meal 5|Meal 6|Meal 7|Meal 8"

    LANGUAGE_PUMP_NAME = {
        0 : "English",
        1 : "Arabic",
        2 : "Chinese",
        3 : "Czech",
        4 : "Danish",
        5 : "Dutch",
        6 : "Finnish",
        7 : "French",
        8 : "German",
        9 : "Greek",
        10: "Hebrew",
        11: "Hungarian",
        12: "Italian",
        13: "Japanese",
        14: "Korean",
        15: "Norwegian",
        16: "Polish",
        17: "Portuguese",
        18: "Russian",
        19: "Slovak",
        20: "Slovenian",
        21: "Spanish",
        22: "Swedish",
        23: "Turkish"
    }



class NGPHistoryEvent:
    class EVENT_TYPE:
        TIME_RESET = 0x02
        USER_TIME_DATE_CHANGE = 0x03
        SOURCE_ID_CONFIGURATION = 0x04
        NETWORK_DEVICE_CONNECTION = 0x05
        AIRPLANE_MODE = 0x06
        START_OF_DAY_MARKER = 0x07
        END_OF_DAY_MARKER = 0x08
        PLGM_CONTROLLER_STATE = 0x0B
        CLOSED_LOOP_STATUS_DATA = 0x0C
        CLOSED_LOOP_PERIODIC_DATA = 0x0D
        CLOSED_LOOP_DAILY_DATA = 0x0E
        NORMAL_BOLUS_PROGRAMMED = 0x15
        SQUARE_BOLUS_PROGRAMMED = 0x16
        DUAL_BOLUS_PROGRAMMED = 0x17
        CANNULA_FILL_DELIVERED = 0x1A
        TEMP_BASAL_PROGRAMMED = 0x1B
        BASAL_PATTERN_SELECTED = 0x1C
        BASAL_SEGMENT_START = 0x1D
        INSULIN_DELIVERY_STOPPED = 0x1E
        INSULIN_DELIVERY_RESTARTED = 0x1F
        SELF_TEST_REQUESTED = 0x20
        SELF_TEST_RESULTS = 0x21
        TEMP_BASAL_COMPLETE = 0x22
        BOLUS_SUSPENDED = 0x24
        SUSPENDED_BOLUS_RESUMED = 0x25
        SUSPENDED_BOLUS_CANCELED = 0x26
        BOLUS_CANCELED = 0x27
        ALARM_NOTIFICATION = 0x28
        ALARM_CLEARED = 0x2A
        LOW_RESERVOIR = 0x2B
        BATTERY_INSERTED = 0x2C
        FOOD_EVENT_MARKER = 0x2E
        EXERCISE_EVENT_MARKER = 0x2F
        INJECTION_EVENT_MARKER = 0x30
        OTHER_EVENT_MARKER = 0x31
        BG_READING = 0x32
        CODE_UPDATE = 0x33
        MISSED_MEAL_BOLUS_REMINDER_EXPIRED = 0x34
        REWIND = 0x36
        BATTERY_REMOVED = 0x37
        CALIBRATION_COMPLETE = 0x38
        ACTIVE_INSULIN_CLEARED = 0x39
        DAILY_TOTALS = 0x3C
        BOLUS_WIZARD_ESTIMATE = 0x3D
        MEAL_WIZARD_ESTIMATE = 0x3E
        CLOSED_LOOP_DAILY_TOTALS = 0x3F
        USER_SETTINGS_SAVE = 0x50
        USER_SETTINGS_RESET_TO_DEFAULTS = 0x51
        OLD_BASAL_PATTERN = 0x52
        NEW_BASAL_PATTERN = 0x53
        OLD_PRESET_TEMP_BASAL = 0x54
        NEW_PRESET_TEMP_BASAL = 0x55
        OLD_PRESET_BOLUS = 0x56
        NEW_PRESET_BOLUS = 0x57
        MAX_BASAL_RATE_CHANGE = 0x58
        MAX_BOLUS_CHANGE = 0x59
        PERSONAL_REMINDER_CHANGE = 0x5A
        MISSED_MEAL_BOLUS_REMINDER_CHANGE = 0x5B
        BOLUS_INCREMENT_CHANGE = 0x5C
        BOLUS_WIZARD_SETTINGS_CHANGE = 0x5D
        OLD_BOLUS_WIZARD_INSULIN_SENSITIVITY = 0x5E
        NEW_BOLUS_WIZARD_INSULIN_SENSITIVITY = 0x5F
        OLD_BOLUS_WIZARD_INSULIN_TO_CARB_RATIOS = 0x60
        NEW_BOLUS_WIZARD_INSULIN_TO_CARB_RATIOS = 0x61
        OLD_BOLUS_WIZARD_BG_TARGETS = 0x62
        NEW_BOLUS_WIZARD_BG_TARGETS = 0x63
        DUAL_BOLUS_OPTION_CHANGE = 0x64
        SQUARE_BOLUS_OPTION_CHANGE = 0x65
        EASY_BOLUS_OPTION_CHANGE = 0x66
        BG_REMINDER_OPTION_CHANGE = 0x68
        BG_REMINDER_TIME = 0x69
        AUDIO_VIBRATE_MODE_CHANGE = 0x6A
        TIME_FORMAT_CHANGE = 0x6B
        # LOW_RESERVOIR_WARNING_CHANGE = 0x6C
        LOW_RESERVOIR_REMINDER_CHANGE = 0x6C
        LANGUAGE_CHANGE = 0x6D
        STARTUP_WIZARD_START_END = 0x6E
        REMOTE_BOLUS_OPTION_CHANGE = 0x6F
        AUTO_SUSPEND_CHANGE = 0x72
        BOLUS_DELIVERY_RATE_CHANGE = 0x73
        DISPLAY_OPTION_CHANGE = 0x77
        SET_CHANGE_REMINDER_CHANGE = 0x78
        BLOCK_MODE_CHANGE = 0x79
        BOLUS_WIZARD_SETTINGS_SUMMARY = 0x7B
        CLOSED_LOOP_BG_READING = 0x82
        CLOSED_LOOP_OPTION_CHANGE = 0x86
        CLOSED_LOOP_SETTINGS_CHANGED = 0x87
        CLOSED_LOOP_TEMP_TARGET_STARTED = 0x88
        CLOSED_LOOP_TEMP_TARGET_ENDED = 0x89
        CLOSED_LOOP_ALARM_AUTO_CLEARED = 0x8A
        SENSOR_SETTINGS_CHANGE = 0xC8
        OLD_SENSOR_WARNING_LEVELS = 0xC9
        NEW_SENSOR_WARNING_LEVELS = 0xCA
#        GENERAL_SENSOR_SETTINGS_CHANGE = 0xCB
        CALIBRATION_REMINDER_CHANGE = 0xCB
        SENSOR_GLUCOSE_READINGS = 0xCC
        SENSOR_GLUCOSE_GAP = 0xCD
        GLUCOSE_SENSOR_CHANGE = 0xCE
        SENSOR_CALIBRATION_REJECTED = 0xCF
        SENSOR_ALERT_SILENCE_STARTED = 0xD0
        SENSOR_ALERT_SILENCE_ENDED = 0xD1
        OLD_LOW_SENSOR_WARNING_LEVELS = 0xD2
        NEW_LOW_SENSOR_WARNING_LEVELS = 0xD3
        OLD_HIGH_SENSOR_WARNING_LEVELS = 0xD4
        NEW_HIGH_SENSOR_WARNING_LEVELS = 0xD5
        SENSOR_GLUCOSE_READINGS_EXTENDED = 0xD6
        NORMAL_BOLUS_DELIVERED = 0xDC
        SQUARE_BOLUS_DELIVERED = 0xDD
        DUAL_BOLUS_PART_DELIVERED = 0xDE
        CLOSED_LOOP_TRANSITION = 0xDF
        GENERATED_SENSOR_GLUCOSE_READINGS_EXTENDED_ITEM = 0xD601  # this is not a pump event, it's generated from single items within SENSOR_GLUCOSE_READINGS_EXTENDED

    def __init__(self, event_data):
        self.event_data = event_data

    @property
    def source(self):
        # No idea what "source" means.
        return BinaryDataDecoder.read_byte(self.event_data, 0x01)  # self.eventData[0x01];

    @property
    def size(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x02)  # this.eventData[0x02];

    @property
    def event_type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x00)  # this.eventData[0];

    @property
    def timestamp(self):
        return DateTimeHelper.decode_date_time(BinaryDataDecoder.read_uint64be(self.event_data, 0x03))

    @property
    def dynamic_action_requestor(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x01)  # self.eventData[0x01];

    def __str__(self):
        return '{0} 0x{1:X} {2} {3}'.format(self.__class__.__name__, self.event_type, self.timestamp,
                                            binascii.hexlify(self.event_data[0x0B:]))

    def __shortstr__(self):
        return '{0} 0x{1:X} {2}'.format(self.__class__.__name__, self.event_type, self.timestamp)

    def __repr__(self):
        return str(self)

    def all_nested_events(self):
        yield self.event_instance()

    def post_process(self, history_events):
        pass

    def event_instance(self):
        if self.event_type == NGPHistoryEvent.EVENT_TYPE.BG_READING:
            return BloodGlucoseReadingEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NORMAL_BOLUS_DELIVERED:
            return NormalBolusDeliveredEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SENSOR_GLUCOSE_READINGS_EXTENDED:
            return SensorGlucoseReadingsEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BOLUS_WIZARD_ESTIMATE:
            return BolusWizardEstimateEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BASAL_SEGMENT_START:
            return BasalSegmentStartEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.INSULIN_DELIVERY_STOPPED:
            return InsulinDeliveryStoppedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.INSULIN_DELIVERY_RESTARTED:
            return InsulinDeliveryRestartedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.PLGM_CONTROLLER_STATE:
            return PLGMControllerStateEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.CALIBRATION_COMPLETE:
            return CalibrationCompleteEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.ALARM_NOTIFICATION:
            return AlarmNotificationEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.ALARM_CLEARED:
            return AlarmClearedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SENSOR_ALERT_SILENCE_STARTED:
            return SensorAlertSilenceStartedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SENSOR_ALERT_SILENCE_ENDED:
            return SensorAlertSilenceEndedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.CALIBRATION_REMINDER_CHANGE:
            return CalibrationReminderChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.DAILY_TOTALS:
            return DailyTotalsEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.START_OF_DAY_MARKER:
            return StartOfDayMarkerEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.END_OF_DAY_MARKER:
            return EndOfDayMarkerEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SOURCE_ID_CONFIGURATION:
            return SourceIdConfigurationEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NORMAL_BOLUS_PROGRAMMED:
            return NormalBolusProgrammedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NETWORK_DEVICE_CONNECTION:
            return NetworkDeviceConnectionEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BASAL_PATTERN_SELECTED:
            return BasalPatternSelectedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.TEMP_BASAL_COMPLETE:
            return TempBasalCompleteEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.CANNULA_FILL_DELIVERED:
            return CannulaFillDeliveredEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.DUAL_BOLUS_PROGRAMMED:
            return DualBolusProgrammedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.TEMP_BASAL_PROGRAMMED:
            return TempBasalProgrammedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.DUAL_BOLUS_PART_DELIVERED:
            return DualBolusPartDeliveredEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SQUARE_BOLUS_PROGRAMMED:
            return SquareBolusProgrammedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SQUARE_BOLUS_DELIVERED:
            return SquareBolusDeliveredEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.OLD_BASAL_PATTERN:
            return OldBasalPatternEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NEW_BASAL_PATTERN:
            return NewBasalPatternEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.LOW_RESERVOIR:
            return LowReservoirEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.DISPLAY_OPTION_CHANGE:
            return DisplayOptionChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.AIRPLANE_MODE:
            return AirplaneModeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.TIME_RESET:
            return TimeResetEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.USER_TIME_DATE_CHANGE:
            return UserTimeDateChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.AUDIO_VIBRATE_MODE_CHANGE:
            return AudioVibrateModeChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.EXERCISE_EVENT_MARKER:
            return ExerciseEventMarkerEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.INJECTION_EVENT_MARKER:
            return InjectionEventMarkerEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.FOOD_EVENT_MARKER:
            return FoodEventMarkerEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.OTHER_EVENT_MARKER:
            return OtherEventMarkerEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SET_CHANGE_REMINDER_CHANGE:
            return SetChangeReminderChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BG_REMINDER_OPTION_CHANGE:
            return BGReminderChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.LOW_RESERVOIR_REMINDER_CHANGE:
            return LowReservoirReminderChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.PERSONAL_REMINDER_CHANGE:
            return PersonalReminderChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.MISSED_MEAL_BOLUS_REMINDER_CHANGE:
            return MissedMealBolusReminderChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.GLUCOSE_SENSOR_CHANGE:
            return GlucoseSensorChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BATTERY_INSERTED:
            return BatteryInsertedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BATTERY_REMOVED:
            return BatteryRemovedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.MISSED_MEAL_BOLUS_REMINDER_EXPIRED:
            return MissedMealBolusReminderExpiredEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SENSOR_CALIBRATION_REJECTED:
            return SensorCalibrationRejectedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SELF_TEST_REQUESTED:
            return SelfTestRequestedEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SELF_TEST_RESULTS:
            return SelfTestResultsEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.REWIND:
            return RewindEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.USER_SETTINGS_RESET_TO_DEFAULTS:
            return UserSettingsResetToDefaultsEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.STARTUP_WIZARD_START_END:
            return StartupWizardStartEndEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.LANGUAGE_CHANGE:
            return LanguageChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.TIME_FORMAT_CHANGE:
            return TimeFormatChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.OLD_BOLUS_WIZARD_INSULIN_TO_CARB_RATIOS:
            return OldBolusWizardInsulinToCarbEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NEW_BOLUS_WIZARD_INSULIN_TO_CARB_RATIOS:
            return NewBolusWizardInsulinToCarbEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.OLD_BOLUS_WIZARD_INSULIN_SENSITIVITY:
            return OldBolusWizardInsulinSensitivityEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NEW_BOLUS_WIZARD_INSULIN_SENSITIVITY:
            return NewBolusWizardInsulinSensitivityEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.OLD_BOLUS_WIZARD_BG_TARGETS:
            return OldBolusWizardBgTargetsEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NEW_BOLUS_WIZARD_BG_TARGETS:
            return NewBolusWizardBgTargetsEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.SQUARE_BOLUS_OPTION_CHANGE:
            return SquareBolusOptionChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.DUAL_BOLUS_OPTION_CHANGE:
            return DualBolusOptionChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BOLUS_INCREMENT_CHANGE:
            return BolusIncrementChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.MAX_BASAL_RATE_CHANGE:
            return MaxBasalRateChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.MAX_BOLUS_CHANGE:
            return MaxBolusChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.EASY_BOLUS_OPTION_CHANGE:
            return EasyBolusOptionChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.AUTO_SUSPEND_CHANGE:
            return AutoSuspendChangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BOLUS_DELIVERY_RATE_CHANGE:
            return BolusDeliveredRateCangeEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.OLD_PRESET_TEMP_BASAL:
            return OldPresetTempBasalEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NEW_PRESET_TEMP_BASAL:
            return NewPresetTempBasalEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.OLD_PRESET_BOLUS:
            return OldPresetBolusEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.NEW_PRESET_BOLUS:
            return NewPresetBolusEvent(self.event_data)
        elif self.event_type == NGPHistoryEvent.EVENT_TYPE.BOLUS_CANCELED:
            return BolusCanceledEvent(self.event_data)
        # elif self.event_type == NGPHistoryEvent.EVENT_TYPE.CLOSED_LOOP_BG_READING:
        #     return ClosedLoopBloodGlucoseReadingEvent(self.eventData)


        return self


class BloodGlucoseReadingEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} BG:{1} ({9}), Source:{2} ({7}), bgUnits:{8} ({3}), "
                "calibrationFlag: {4}, meterSerialNumber: {5}, "
                "isCalibration: {6}").format(NGPHistoryEvent.__shortstr__(self),
                                             self.bg_value, self.bg_source_name, self.bg_units,
                                             self.calibration_flag, self.meter_serial_number, self.is_calibration,
                                             self.bg_source, self.bg_units_name, self.bg_value_mmol)

    @property
    def bg_value(self):
        # bgValue is always in mg/dL.
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0C)

    @property
    def bg_value_mmol(self):
        return round(self.bg_value / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1)

    @property
    def bg_source(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0E)

    @property
    def bg_source_name(self):
        return NGPConstants.BG_SOURCE_NAME[self.bg_source]

    @property
    def bg_units(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B) & 1

    @property
    def bg_units_name(self):
        return NGPConstants.BG_UNITS_NAME[self.bg_units]

    @property
    def calibration_flag(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x0B) & 2) == 2

    @property
    def meter_serial_number(self):
        return (self.event_data[0x0F:]).decode('utf-8')[::-1]

    @property
    def is_calibration(self):
        if self.bg_source == NGPConstants.BG_SOURCE.SENSOR_CAL or self.calibration_flag:
            return True
        else:
            return False

class BolusDeliveredEvent(NGPHistoryEvent):

    @property
    def bolus_source(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def bolus_source_name(self):
        return NGPConstants.BOLUS_SOURCE_NAME[self.bolus_source]

    @property
    def bolus_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def preset_bolus_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def preset_bolus_number_name(self):
        return NGPConstants.BOLUS_PRESET_NAME[self.preset_bolus_number]

class NormalBolusDeliveredEvent(BolusDeliveredEvent):
    def __init__(self, event_data):
        BolusDeliveredEvent.__init__(self, event_data)
        self.canceled = False

    def __str__(self):
        return ("{0} Source:{1} ({2}), Bolus number:{3}, Preset:{8} ({4}), "
               "Programmed: {5}, Delivered:{6}, Active:{7}, Canceled:{9}").format(NGPHistoryEvent.__shortstr__(self),
                                                                    self.bolus_source_name, self.bolus_source,
                                                                    self.bolus_number, self.preset_bolus_number,
                                                                    self.programmed_amount, self.delivered_amount,
                                                                    self.active_insulin, self.preset_bolus_number_name, self.canceled)

    @property
    def programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

    @property
    def delivered_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x12) / 10000.0

    @property
    def active_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x16) / 10000.0

    def post_process(self, history_events):
        matches = [x for x in history_events
                   if isinstance(x, NormalBolusProgrammedEvent)
                   and x.bolus_number == self.bolus_number
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=5)]
        if len(matches) == 1:
            self.programmedEvent = matches[0]

        matches = [x for x in history_events
                   if isinstance(x, BolusCanceledEvent)
                   and x.bolus_number == self.bolus_number
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=5)]
        if len(matches) == 1:
            self.canceledEvent = matches[0]
            self.canceled = True


class BolusProgrammedEvent(NGPHistoryEvent):

    @property
    def bolus_source(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def bolus_source_name(self):
        return NGPConstants.BOLUS_SOURCE_NAME[self.bolus_source]

    @property
    def bolus_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def preset_bolus_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def preset_bolus_number_name(self):
        return NGPConstants.BOLUS_PRESET_NAME[self.preset_bolus_number]

class NetworkDeviceConnectionEvent (NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} OldStatus:{1}, NewStatus:{2}, Value1:{3}, Serial:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                          self.flag1, self.flag2,
                                                                          self.value1, self.serial)

    @property
    def flag1(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x0B) & 0x01) == 1

    @property
    def value1(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def flag2(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x0D) & 0x01) == 1

    @property
    def serial(self):
        return (self.event_data[0x0E:]).decode('utf-8')[::-1]

class BasalPatternSelectedEvent (NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} oldPatternNumber:{1} ({2}), newPatternNumber:{3} ({4})'.format(NGPHistoryEvent.__shortstr__(self),
                                                                       self.old_pattern_name, self.old_pattern_number,
                                                                       self.new_pattern_name, self.new_pattern_number)

    @property
    def old_pattern_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_pattern_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_pattern_name(self):
        return NGPConstants.BASAL_PATTERN_NAME[self.old_pattern_number]

    @property
    def new_pattern_name(self):
        return NGPConstants.BASAL_PATTERN_NAME[self.new_pattern_number]

class TempBasalCompleteEvent (NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Preset:{1} ({2}), Type:{3} ({9}), "
                "Rate:{4}, Percent:{5}%, Duration:{6}(Minutes), Canceled:{7}, DurationLeft:{8}(Minutes)").format(NGPHistoryEvent.__shortstr__(self),
                                                                          self.preset_name, self.preset, self.type,
                                                                          self.rate, self.percentage_of_rate,
                                                                          self.duration,self.canceled, self.duration_left, self.type_name)

    @property
    def preset(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def preset_name(self):
        return NGPConstants.TEMP_BASAL_PRESET_NAME[self.preset]

    @property
    def type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def type_name(self):
        return NGPConstants.TEMP_BASAL_TYPE_NAME[self.type]

    @property
    def rate(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0D) / 10000.0

    @property
    def percentage_of_rate(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x11)

    @property
    def duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x12)

    @property
    def canceled(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x14) & 0x01) == 1

    @property
    def duration_left(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x15)

class CannulaFillDeliveredEvent (NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Type:{4} (1), Delivered:{2}, "
                "Remaining:{3}").format(NGPHistoryEvent.__shortstr__(self),
                                      self.type, self.delivered,
                                      self.remaining, self.type_name)

    @property
    def type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def type_name(self):
        return NGPConstants.CANNULA_FILL_TYPE[self.type]

    @property
    def delivered(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0C) / 10000.0

    @property
    def remaining(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x10) / 10000.0

class NormalBolusProgrammedEvent(BolusProgrammedEvent):
    def __init__(self, event_data):
        BolusProgrammedEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Source:{1} ({2}), Bolus number:{3}, Preset:{4} ({7}), "
               "Programmed: {5}, Active:{6}").format(BolusProgrammedEvent.__shortstr__(self),
                                                     self.bolus_source_name, self.bolus_source,
                                                     self.bolus_number, self.preset_bolus_number_name,
                                                     self.programmed_amount, self.active_insulin, self.preset_bolus_number)

    @property
    def programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

    @property
    def active_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x12) / 10000.0

    def post_process(self, history_events):
        matches = [x for x in history_events
                   if isinstance(x, BolusWizardEstimateEvent)
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=5)
                   and x.final_estimate == self.programmed_amount]
        if len(matches) == 1:
            self.bolusWizardEvent = matches[0]
            self.bolusWizardEvent.programmed = True

class DualBolusProgrammedEvent(BolusProgrammedEvent):
    def __init__(self, event_data):
        BolusProgrammedEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Source:{1} ({2}), Bolus number:{3}, Preset:{4} ({9}), "
               "Normal: {5}, Square:{6}, Duration:{7}(Minutes), Active:{8}").format(
            BolusProgrammedEvent.__shortstr__(self),
            self.bolus_source_name, self.bolus_source,
            self.bolus_number, self.preset_bolus_number_name,
            self.normal_programmed_amount, self.square_programmed_amount,
            self.programmed_duration, self.active_insulin, self.preset_bolus_number)

    @property
    def normal_programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

    @property
    def square_programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x12) / 10000.0

    @property
    def programmed_duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x16)

    @property
    def active_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x18) / 10000.0

    @property
    def programmed_amount(self):
        return round(self.normal_programmed_amount + self.square_programmed_amount, 1)

    def post_process(self, history_events):
        matches = [x for x in history_events
                   if isinstance(x, BolusWizardEstimateEvent)
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=5)
                   and x.final_estimate == self.programmed_amount]
        if len(matches) == 1:
            self.bolusWizardEvent = matches[0]
            self.bolusWizardEvent.programmed = True


class DualBolusPartDeliveredEvent(BolusDeliveredEvent):
    def __init__(self, event_data):
        BolusDeliveredEvent.__init__(self, event_data)
        self.canceled = False

    def __str__(self):
        return ("{0} Source:{1} ({2}), Bolus number:{3}, Preset:{4} ({13}), "
                "Normal: {5}, Square:{6}, Duration:{7}(Minutes), "
                "Active:{8}, DeliveredAmount:{9}, BolusPart:{10} ({11}), "
                "DeliveredDuration:{12}, Canceled:{14}").format(BolusDeliveredEvent.__shortstr__(self),
                                                self.bolus_source_name, self.bolus_source,
                                                self.bolus_number, self.preset_bolus_number_name,
                                                self.normal_programmed_amount, self.square_programmed_amount,
                                                self.programmed_duration, self.active_insulin,
                                                self.delivered_amount,self.bolus_part_name, self.bolus_part,
                                                self.delivered_duration, self.preset_bolus_number, self.canceled)

    @property
    def normal_programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

    @property
    def square_programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x12) / 10000.0

    @property
    def delivered_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x16) / 10000.0

    @property
    def bolus_part(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x1A)

    @property
    def bolus_part_name(self):
        return NGPConstants.DUAL_BOLUS_PART_NAME[self.bolus_part]

    @property
    def programmed_duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x1B)

    @property
    def delivered_duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x1D)

    @property
    def active_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x1F) / 10000.0

    def post_process(self, history_events):
        matches = [x for x in history_events
                   if isinstance(x, DualBolusProgrammedEvent)
                   and x.bolus_number == self.bolus_number
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=self.programmed_duration)]
        if len(matches) == 1:
            self.programmedEvent = matches[0]

        matches = [x for x in history_events
                   if isinstance(x, BolusCanceledEvent)
                   and x.bolus_number == self.bolus_number
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=self.programmed_duration)]
        if len(matches) == 1:
            self.canceledEvent = matches[0]
            self.canceled = True


class SquareBolusProgrammedEvent(BolusProgrammedEvent):
    def __init__(self, event_data):
        BolusProgrammedEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Source:{1} ({2}), Bolus number:{3}, Preset:{4} ({8}), "
                "ProgrammedAmount: {5}, ProgrammedDuration:{6}(Minutes), "
                "Active:{7}").format(BolusProgrammedEvent.__shortstr__(self),
                            self.bolus_source_name, self.bolus_source,
                            self.bolus_number, self.preset_bolus_number_name,
                            self.programmed_amount, self.programmed_duration,
                            self.active_insulin, self.preset_bolus_number)

    @property
    def programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

    @property
    def programmed_duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x12)

    @property
    def active_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x14) / 10000.0

    def post_process(self, history_events):
        matches = [x for x in history_events
                   if isinstance(x, BolusWizardEstimateEvent)
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=5)
                   and x.final_estimate == self.programmed_amount]
        if len(matches) == 1:
            self.bolusWizardEvent = matches[0]
            self.bolusWizardEvent.programmed = True

class SquareBolusDeliveredEvent(BolusDeliveredEvent):
    def __init__(self, event_data):
        BolusDeliveredEvent.__init__(self, event_data)
        self.canceled = False

    def __str__(self):
        return ("{0} Source:{1} ({2}), Bolus number:{3}, Preset:{4} ({10}), "
                "ProgrammedAmount: {5}, DeliveredAmount:{6}, "
                "ProgrammedDuration:{7}(Minutes), DeliveredDuration:{8}(Minutes), "
                "Active:{9}, Canceled:{11}").format(BolusDeliveredEvent.__shortstr__(self),
                                    self.bolus_source_name, self.bolus_source,
                                    self.bolus_number, self.preset_bolus_number_name,
                                    self.programmed_amount, self.delivered_amount,
                                    self.programmed_duration, self.delivered_duration,
                                    self.active_insulin, self.preset_bolus_number, self.canceled)

    @property
    def programmed_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

    @property
    def delivered_amount(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x12) / 10000.0

    @property
    def programmed_duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x16)

    @property
    def delivered_duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x18)

    @property
    def active_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x1A) / 10000.0

    def post_process(self, history_events):
        matches = [x for x in history_events
                   if isinstance(x, SquareBolusProgrammedEvent)
                   and x.bolus_number == self.bolus_number
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=self.programmed_duration)]
        if len(matches) == 1:
            self.programmedEvent = matches[0]

        matches = [x for x in history_events
                   if isinstance(x, BolusCanceledEvent)
                   and x.bolus_number == self.bolus_number
                   and x.timestamp < self.timestamp
                   and self.timestamp - x.timestamp < timedelta(minutes=self.programmed_duration)]
        if len(matches) == 1:
            self.canceledEvent = matches[0]
            self.canceled = True

class TempBasalProgrammedEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Preset:{1} ({2}), Type:{3} ({4}), Rate:{5}, "
               "Percent:{6}%, Duration:{6}(Minutes)").format(NGPHistoryEvent.__shortstr__(self),
                                                             self.preset_name, self.preset,
                                                             self.type, self.type_name, self.rate,
                                                             self.percentage_of_rate, self.duration)

    @property
    def preset(self):
        # NGPConstants.TEMP_BASAL_TYPE
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def preset_name(self):
        # NGPConstants.TEMP_BASAL_PRESET_NAME
        return NGPConstants.TEMP_BASAL_PRESET_NAME[self.preset]

    @property
    def type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def type_name(self):
        return NGPConstants.TEMP_BASAL_TYPE_NAME[self.type]

    @property
    def rate(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0D) / 10000.0

    @property
    def percentage_of_rate(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x11)

    @property
    def duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x12)

class BasalPatternEvent(NGPHistoryEvent):

    @property
    def pattern_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def pattern_name(self):
        return NGPConstants.BASAL_PATTERN_NAME[self.pattern_number]

    @property
    def number_of_segments(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def segments(self):
        segments = {}
        pos = 0x0D
        for i in range(self.number_of_segments):
            rate = BinaryDataDecoder.read_uint32be(self.event_data, pos) / 10000.0
            start = (BinaryDataDecoder.read_byte(self.event_data, pos + 4) * 30)
            time = str(timedelta(minutes=start))
            seg = {
                "rate" : rate,
                "start_minutes" : start,
                "time_str" : time
            }
            segments.update({ "{0}".format(i+1) : seg })
            pos = pos + 0x05
        return segments

class OldBasalPatternEvent(BasalPatternEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Pattern:{1} ({2}), SegmentsNumber:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                    self.pattern_name, self.pattern_number,
                                                                    self.number_of_segments,self.segments)

class NewBasalPatternEvent(BasalPatternEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Pattern:{1} ({2}), SegmentsNumber:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                    self.pattern_name, self.pattern_number,
                                                                    self.number_of_segments,self.segments)

class LowReservoirEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Type:{1}, Hours:{2}, Minutes:{3}, Units:{4}").format(NGPHistoryEvent.__shortstr__(self),
                                                                          self.warning_type, self.hours_remaining,
                                                                          self.minutes_remaining,self.units_remaining)

    @property
    def warning_type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    # TODO change time format
    @property
    def hours_remaining(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def minutes_remaining(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def units_remaining(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

class DisplayOptionChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} OldBrightness:{1}, NewBrightness:{2}, OldBacklight:{3} Sec, NewBacklight:{4} Sec").format(
                    NGPHistoryEvent.__shortstr__(self),
                    self.old_brightness_level, self.new_brightness_level, self.old_backlight_seconds, self.new_backlight_seconds)

    @property
    def old_brightness_level(self):
        return "Auto" if BinaryDataDecoder.read_byte(self.event_data, 0x0B) == 0 else BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    # TODO change time format
    @property
    def old_backlight_seconds(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def new_brightness_level(self):
        return "Auto" if BinaryDataDecoder.read_byte(self.event_data, 0x0F) == 0 else BinaryDataDecoder.read_byte(self.event_data, 0x0F)

    # TODO change time format
    @property
    def new_backlight_seconds(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x11)

class AudioVibrateModeChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} OldVolumeLevel:{1}, NewVolumeLevel:{2}, OldMode:{3} ({4}), NewMode:{5} ({6})").format(
                NGPHistoryEvent.__shortstr__(self),
                self.old_volume_level, self.new_volume_level, self.old_mode_name, self.old_mode, self.new_mode_name, self.new_mode)

    @property
    def old_mode(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def old_mode_name(self):
        return NGPConstants.AUDIO_MODE_NAME[self.old_mode]

    @property
    def old_volume_level(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def new_mode(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def new_mode_name(self):
        return NGPConstants.AUDIO_MODE_NAME[self.new_mode]

    @property
    def new_volume_level(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0E)

class ExerciseEventMarkerEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} DateTime:{1}, Duration:{2}").format(
                NGPHistoryEvent.__shortstr__(self),
                self.timestamp, str(timedelta(minutes=self.duration_minutes)))

    @property
    def timestamp(self):
        return DateTimeHelper.decode_date_time(BinaryDataDecoder.read_uint64be(self.event_data, 0x0B))

    @property
    def duration_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x13)

class InjectionEventMarkerEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} DateTime:{1}, Injection:{2} U").format(
                NGPHistoryEvent.__shortstr__(self),
                self.timestamp, self.injection)

    @property
    def timestamp(self):
        return DateTimeHelper.decode_date_time(BinaryDataDecoder.read_uint64be(self.event_data, 0x0B))

    @property
    def injection(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x13) / 10000.0

class FoodEventMarkerEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} DateTime:{1}, Type:{2} ({3}), Carb:{4}").format(
                NGPHistoryEvent.__shortstr__(self),
                self.timestamp, self.carb_units_name, self.carb_units, self.carb_input)

    @property
    def timestamp(self):
        return DateTimeHelper.decode_date_time(BinaryDataDecoder.read_uint64be(self.event_data, 0x0B))

    @property
    def carb_units(self):
        # See NGPUtil.NGPConstants.CARB_UNITS
        return BinaryDataDecoder.read_byte(self.event_data, 0x13)  # carbUnits

    @property
    def carb_units_name(self):
        # See NGPUtil.NGPConstants.CARB_UNITS
        return NGPConstants.CARB_UNITS_NAME[self.carb_units]

    @property
    def carb_input(self):
        carbs = BinaryDataDecoder.read_uint16be(self.event_data, 0x14)  # carbInput
        return carbs if self.carb_units == NGPConstants.CARB_UNITS.GRAMS else carbs / 10.0

class OtherEventMarkerEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0}").format(
                NGPHistoryEvent.__shortstr__(self))

class SetChangeReminderChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} OldStatus:{1} ({2}), NewStatus:{3} ({4}), OldDays:{5}, NewDays:{6}").format(
                NGPHistoryEvent.__shortstr__(self),self.old_status_name, self.old_status, self.new_status_name,
            self.new_status, self.old_days, self.new_days)

    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def old_status_name(self):
        return "On" if self.old_status == 1 else "Off"
    @property
    def new_status_name(self):
        return "On" if self.new_status == 1 else "Off"

    @property
    def old_days(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def new_days(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0E)

class BGReminderChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} OldStatus:{1} ({2}), NewStatus:{3} ({4})").format(
                NGPHistoryEvent.__shortstr__(self),self.old_status_name, self.old_status, self.new_status_name,
            self.new_status)

    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_status_name(self):
        return "On" if self.old_status == 1 else "Off"
    @property
    def new_status_name(self):
        return "On" if self.new_status == 1 else "Off"

class LowReservoirReminderChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} OldUnits:{1}, NewUnits:{2}, OldType:{3}({4}), NewType:{5} ({6}), OldMinutes:{7}, NewMinutes:{8}").format(
            NGPHistoryEvent.__shortstr__(self),self.old_units, self.new_units, self.old_type_name, self.old_type,
            self.new_type_name, self.new_type, str(timedelta(minutes=self.old_minutes)), str(timedelta(minutes=self.new_minutes)) )

    @property
    def new_units(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x15) / 10000.0

    @property
    def old_units(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E) / 10000.0

    @property
    def new_type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x12)

    @property
    def old_type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x13)

    @property
    def old_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0C)

    @property
    def new_type_name(self):
        return "Time" if self.new_type == 1 else "Units"

    @property
    def old_type_name(self):
        return "Time" if self.old_type == 1 else "Units"

class PersonalReminderChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Reminder:{1}, IsReminder:{2}, InList:{3}, OldEnable:{4}, NewEnable:{5}, OldTime:{6}, NewTime:{7}").format(
            NGPHistoryEvent.__str__(self),self.reminder_name, self.is_reminder_name, self.in_list_name,
            self.old_status_enable_name, self.new_status_enable_name,
            str(timedelta(minutes=self.old_minutes)), str(timedelta(minutes=self.new_minutes)) )

    @property
    def reminder(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def reminder_name(self):
        list = NGPConstants.ALARM_PERSONAL_REMINDER.split("|")
        index = self.reminder - 1
        if index >= 0 and index <= len(list):
            return list[index]
        else:
            return "~"

    @property
    def old_status_enable(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0F)

    @property
    def new_status_enable(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x13)

    @property
    def old_status_enable_name(self):
        return "On" if self.old_status_enable == 1 else "Off"

    @property
    def new_status_enable_name(self):
        return "On" if self.new_status_enable == 1 else "Off"

    @property
    def new_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x11)

    @property
    def old_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0D)

    @property
    def is_reminder(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)
    @property
    def is_reminder_name(self):
        return "Yes" if self.new_status_enable == 1 else "No"

    @property
    def in_list(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x10)

    @property
    def in_list_name(self):
        return "Yes" if self.new_status_enable == 1 else "No"

class MissedMealBolusReminderChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Reminder:{1}, IsReminder:{2}, InList:{3}, OldEnable:{4}, NewEnable:{5}, OldTime:{6}-{7}, NewTime:{8}-{9}").format(
            NGPHistoryEvent.__str__(self),self.reminder_name, self.is_reminder_name, self.in_list_name,
            self.old_status_enable_name, self.new_status_enable_name,
            str(timedelta(minutes=self.old_start_minutes)), str(timedelta(minutes=self.old_end_minutes)),
            str(timedelta(minutes=self.new_start_minutes)), str(timedelta(minutes=self.new_end_minutes)) )

    @property
    def reminder(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def reminder_name(self):
        list = NGPConstants.ALARM_MISSED_MEAL_BOLUS_REMINDER.split("|")
        index = self.reminder - 1
        if index >= 0 and index <= len(list):
            return list[index]
        else:
            return "~"

    @property
    def new_start_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x13)

    @property
    def new_end_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x15)

    @property
    def old_start_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0D)

    @property
    def old_end_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0F)

    @property
    def old_status_enable(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x11)

    @property
    def new_status_enable(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x17)

    @property
    def old_status_enable_name(self):
        return "On" if self.old_status_enable == 1 else "Off"

    @property
    def new_status_enable_name(self):
        return "On" if self.new_status_enable == 1 else "Off"

    @property
    def is_reminder(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)
    @property
    def is_reminder_name(self):
        return "Yes" if self.new_status_enable == 1 else "No"

    @property
    def in_list(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x12)

    @property
    def in_list_name(self):
        return "Yes" if self.new_status_enable == 1 else "No"

class GlucoseSensorChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0}").format(NGPHistoryEvent.__shortstr__(self))

class BatteryInsertedEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0}").format(NGPHistoryEvent.__shortstr__(self))

class BatteryRemovedEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0}").format(NGPHistoryEvent.__shortstr__(self))

class AirplaneModeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Status:{1} ({2})").format(NGPHistoryEvent.__shortstr__(self),self.switch_name, self.switch)

    @property
    def switch(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def switch_name(self):
        return "On" if self.switch == 1 else "Off"

class MissedMealBolusReminderExpiredEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Status:{1} ({2})").format(NGPHistoryEvent.__shortstr__(self),self.switch_name, self.switch)

    @property
    def switch(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def switch_name(self):
        return "On" if self.switch == 1 else "Off"

class SensorCalibrationRejectedEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Status:{1} ({2})").format(NGPHistoryEvent.__shortstr__(self),self.switch_name, self.switch)

    @property
    def switch(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def switch_name(self):
        return "On" if self.switch == 1 else "Off"

class SelfTestResultsEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Status:{1} ({2})").format(NGPHistoryEvent.__shortstr__(self),self.switch_name, self.switch)

    @property
    def switch(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def switch_name(self):
        return "Ok" if self.switch == 1 else "Error"

class SelfTestRequestedEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0}").format(NGPHistoryEvent.__shortstr__(self))

class RewindEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0}").format(NGPHistoryEvent.__shortstr__(self))

class UserSettingsResetToDefaultsEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0}").format(NGPHistoryEvent.__shortstr__(self))

class StartupWizardStartEndEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Status: {1} ({2})").format(NGPHistoryEvent.__shortstr__(self), self.status_name, self.status)

    @property
    def status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def status_name(self):
        return "End" if self.status == 1 else "Start"

class LanguageChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old:{1} ({2}), New:{3} ({4})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_language, self.old_number,
            self.new_language, self.new_number)

    @property
    def old_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_language(self):
        return NGPConstants.LANGUAGE_PUMP_NAME[self.old_number]

    @property
    def new_language(self):
        return NGPConstants.LANGUAGE_PUMP_NAME[self.new_number]

class TimeFormatChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old:{1} ({2}), New:{3} ({4})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_time_format_name, self.old_number,
            self.new_time_format_name, self.new_number)

    @property
    def old_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_time_format_name(self):
        return "12h" if self.old_number == 0 else "24h"

    @property
    def new_time_format_name(self):
        return "12h" if self.new_number == 0 else "24h"

class BolusWizardInsulinToCarbEvent(NGPHistoryEvent):

    @property
    def carb_units(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B) # 0=grams 1=exchanges

    @property
    def carb_units_name(self):
        return NGPConstants.CARB_UNITS_NAME[self.carb_units]

    @property
    def number_of_segments(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def segments(self):
        segments = {}
        pos = 0x0D
        for i in range(self.number_of_segments):
            start = (BinaryDataDecoder.read_byte(self.event_data, pos) * 30)
            amount_tmp = BinaryDataDecoder.read_uint32be(self.event_data, pos + 1)
            amount = amount_tmp / 10.0 if (self.carb_units == NGPConstants.CARB_UNITS.GRAMS) else amount_tmp / 1000.0

            time = str(timedelta(minutes=start))
            seg = {
                "amount" : amount,
                "start_minutes" : start,
                "time_str" : time
            }
            segments.update({ "{0}".format(i+1) : seg })
            pos = pos + 0x05
        return segments

class OldBolusWizardInsulinToCarbEvent(BolusWizardInsulinToCarbEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Units:{1} ({2}), SegmentsNumbers:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                                self.carb_units_name, self.carb_units,
                                                                                self.number_of_segments, self.segments)

class NewBolusWizardInsulinToCarbEvent(BolusWizardInsulinToCarbEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Units:{1} ({2}), SegmentsNumbers:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                                self.carb_units_name, self.carb_units,
                                                                                self.number_of_segments, self.segments)

class BolusWizardInsulinSensitivityEvent(NGPHistoryEvent):

    @property
    def bg_units(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B) # 0=mgdl 1=mmol

    @property
    def bg_units_name(self):
        return NGPConstants.BG_UNITS_NAME[self.bg_units]

    @property
    def number_of_segments(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def segments(self):
        segments = {}
        pos = 0x0D
        for i in range(self.number_of_segments):
            start = (BinaryDataDecoder.read_byte(self.event_data, pos) * 30)
            amount_tmp = BinaryDataDecoder.read_uint16be(self.event_data, pos + 1)
            amount = amount_tmp if self.bg_units == NGPConstants.BG_UNITS.MG_DL else amount_tmp / 10.0

            time = str(timedelta(minutes=start))
            seg = {
                "amount" : amount,
                "start_minutes" : start,
                "time_str" : time
            }
            segments.update({ "{0}".format(i+1) : seg })
            pos = pos + 0x03
        return segments

class OldBolusWizardInsulinSensitivityEvent(BolusWizardInsulinSensitivityEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Units:{1} ({2}), SegmentsNumbers:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                               self.bg_units_name, self.bg_units,
                                                                               self.number_of_segments, self.segments)

class NewBolusWizardInsulinSensitivityEvent(BolusWizardInsulinSensitivityEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Units:{1} ({2}), SegmentsNumbers:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                               self.bg_units_name, self.bg_units,
                                                                               self.number_of_segments, self.segments)

class BolusWizardBgTargetsEvent(NGPHistoryEvent):

    @property
    def bg_units(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B) # 0=mgdl 1=mmol

    @property
    def bg_units_name(self):
        return NGPConstants.BG_UNITS_NAME[self.bg_units]

    @property
    def number_of_segments(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def segments(self):
        segments = {}
        pos = 0x0D
        for i in range(self.number_of_segments):
            start = (BinaryDataDecoder.read_byte(self.event_data, pos) * 30)
            high_tmp = BinaryDataDecoder.read_uint16be(self.event_data, pos + 1)
            high = high_tmp if self.bg_units == NGPConstants.BG_UNITS.MG_DL else high_tmp / 10.0
            low_tmp = BinaryDataDecoder.read_uint16be(self.event_data, pos + 1)
            low = low_tmp if self.bg_units == NGPConstants.BG_UNITS.MG_DL else low_tmp / 10.0

            time = str(timedelta(minutes=start))
            seg = {
                "start_minutes" : start,
                "high" : high,
                "low" : low,
                "time_str" : time
            }
            segments.update({ "{0}".format(i+1) : seg })
            pos = pos + 0x05
        return segments

class OldBolusWizardBgTargetsEvent(BolusWizardBgTargetsEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Units:{1} ({2}), SegmentsNumbers:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                               self.bg_units_name, self.bg_units,
                                                                               self.number_of_segments, self.segments)

class NewBolusWizardBgTargetsEvent(BolusWizardBgTargetsEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Units:{1} ({2}), SegmentsNumbers:{3}, Segments:{4}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                               self.bg_units_name, self.bg_units,
                                                                               self.number_of_segments, self.segments)

class BolusOptionChangeEvent(NGPHistoryEvent):
    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_status_name(self):
        return "Off" if self.old_status == 0 else "On"

    @property
    def new_status_name(self):
        return "Off" if self.new_status == 0 else "On"

class SquareBolusOptionChangeEvent(BolusOptionChangeEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old Status:{1} ({2}), New Status:{3} ({4})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_status_name, self.old_status,
            self.new_status_name, self.new_status,
        )

class DualBolusOptionChangeEvent(BolusOptionChangeEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old Status:{1} ({2}), New Status:{3} ({4})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_status_name, self.old_status,
            self.new_status_name, self.new_status,
        )

class BolusIncrementChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old Status:{1} ({2}), New Status:{3} ({4})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_status_name, self.old_status,
            self.new_status_name, self.new_status,
        )

    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_status_name(self):
        return NGPConstants.BOLUS_STEP_SIZE_NAME[self.old_status]

    @property
    def new_status_name(self):
        return NGPConstants.BOLUS_STEP_SIZE_NAME[self.new_status]

class MaxBasalRateChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old Rate:{1}, New Rate:{2}").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_max_basal_rate, self.new_max_basal_rate)

    @property
    def old_max_basal_rate(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x0B) / 10000.0 )

    @property
    def new_max_basal_rate(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x0F) / 10000.0 )

class MaxBolusChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old Rate:{1}, New Rate:{2}").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_max_bolus, self.new_max_bolus)

    @property
    def old_max_bolus(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x0B) / 10000.0 )

    @property
    def new_max_bolus(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x0F) / 10000.0 )

class EasyBolusOptionChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old state:{1} ({2}), New state:{3} ({4}), Old step:{5}, New step:{6}").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_status_name, self.old_status,
            self.new_status_name, self.new_status,
            self.old_bolus_step, self.new_bolus_step,
        )

    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_status_name(self):
        return "Off" if self.old_status == 0 else "On"

    @property
    def new_status_name(self):
        return "Off" if self.new_status == 0 else "On"

    @property
    def old_bolus_step(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x0D) / 10000.0 )

    @property
    def new_bolus_step(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x11) / 10000.0 )

class AutoSuspendChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old state:{1} ({2}), New state:{3} ({4}), Old time:{5} ({7}), New time:{6} ({8})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_status_name, self.old_status,
            self.new_status_name, self.new_status,
            self.old_time, self.new_time,
            self.old_time_minutes, self.new_time_minutes,
        )

    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def old_status_name(self):
        return "Off" if self.old_status == 0 else "On"

    @property
    def new_status_name(self):
        return "Off" if self.new_status == 0 else "On"

    @property
    def old_time_minutes(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x0C) * 60 )

    @property
    def new_time_minutes(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x0E) * 60 )

    @property
    def old_time(self):
        return str(timedelta(minutes=self.old_time_minutes))

    @property
    def new_time(self):
        return str(timedelta(minutes=self.new_time_minutes))

class BolusDeliveredRateCangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Old state:{1} ({2}), New state:{3} ({4})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.old_status_name, self.old_status,
            self.new_status_name, self.new_status
        )

    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def old_status_name(self):
        return "Standard" if self.old_status == 0 else "Fast"

    @property
    def new_status_name(self):
        return "Standard" if self.new_status == 0 else "Fast"

class PresetTempBasalEvent(NGPHistoryEvent):

    @property
    def preset(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def preset_name(self):
        return NGPConstants.TEMP_BASAL_PRESET_NAME[self.preset]

    @property
    def enable(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def enable_name(self):
        return "Off" if self.enable == 0 else "On"

    @property
    def type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

    @property
    def type_name(self):
        return NGPConstants.TEMP_BASAL_TYPE_NAME[self.type]

    @property
    def rate(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0E)

    @property
    def perc(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x12)

    @property
    def duration_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x13)

    @property
    def duration(self):
        return str(timedelta(minutes=self.duration_minutes))

class OldPresetTempBasalEvent(PresetTempBasalEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Preset:{1} ({2}), State:{3} ({4}), Percent\Rate:{5}, Rate:{6}, Perc:{7}, Duration:{8} ({9})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.preset_name, self.preset,
            self.enable_name, self.enable,
            self.type_name, self.rate, self.perc, self.duration, self.duration_minutes)

class NewPresetTempBasalEvent(PresetTempBasalEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Preset:{1} ({2}), State:{3} ({4}), Percent\Rate:{5}, Rate:{6}, Perc:{7}, Duration:{8} ({9})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.preset_name, self.preset,
            self.enable_name, self.enable,
            self.type_name, self.rate, self.perc, self.duration, self.duration_minutes)

class PresetBolusEvent(NGPHistoryEvent):

    @property
    def preset(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def preset_name(self):
        return NGPConstants.BOLUS_PRESET_NAME[self.preset]

    @property
    def type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def type_name(self):
        return NGPConstants.DUAL_BOLUS_PART_NAME[self.type]

    @property
    def now_rate(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x0D) / 10000.0)

    @property
    def square_rate(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x11) / 10000.0)

    @property
    def duration_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x15)

    @property
    def duration(self):
        return str(timedelta(minutes=self.duration_minutes))

class OldPresetBolusEvent(PresetBolusEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Preset Bolus:{1} ({2}), Type:{3} ({4}), Now rate:{5}, Square rate:{6}, Duration:{7} ({8})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.preset_name, self.preset,
            self.type_name, self.type,
            self.now_rate, self.square_rate, self.duration, self.duration_minutes)

class NewPresetBolusEvent(PresetBolusEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Preset Bolus:{1} ({2}), Type:{3} ({4}), Now rate:{5}, Square rate:{6}, Duration:{7} ({8})").format(
            NGPHistoryEvent.__shortstr__(self),
            self.preset_name, self.preset,
            self.type_name, self.type,
            self.now_rate, self.square_rate, self.duration, self.duration_minutes)

class BolusCanceledEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} Canceled type:{1} ({2}), Bolus number:{3}, Unknown:{4}").format(
            NGPHistoryEvent.__shortstr__(self), self.canceled_type_name, self.canceled_type, self.bolus_number, self.unknown )

    @property
    def canceled_type(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def canceled_type_name(self):
        return "auto" if self.canceled_type == 0 else "manual"

    @property
    def bolus_number(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def unknown(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0D)

class TimeResetEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} NewDate:{1}").format(NGPHistoryEvent.__shortstr__(self),self.date)

    @property
    def datetime(self):
        return BinaryDataDecoder.read_uint64be(self.event_data, 0x0B)

    @property
    def date(self):
        return DateTimeHelper.decode_date_time(self.datetime)

    @property
    def offset(self):
        return DateTimeHelper.decode_date_time_offset(self.datetime)

class UserTimeDateChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return ("{0} NewDate:{1}").format(NGPHistoryEvent.__shortstr__(self),self.date)

    @property
    def datetime(self):
        return BinaryDataDecoder.read_uint64be(self.event_data, 0x0B)

    @property
    def date(self):
        return DateTimeHelper.decode_date_time(self.datetime)

    @property
    def offset(self):
        return DateTimeHelper.decode_date_time_offset(self.datetime)

class SensorGlucoseReadingsEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0}'.format(NGPHistoryEvent.__shortstr__(self))

    @property
    def minutes_between_readings(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B) # minutesBetweenReadings

    @property
    def number_of_readings(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)  # numberOfReadings

    @property
    def predicted_sg(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0D)  # predictedSg

    def all_nested_events(self):
        pos = 0x0F
        for i in range(self.number_of_readings - 1, -1, -1):

            timestamp = self.timestamp - timedelta(minutes=i * self.minutes_between_readings)
            sg = BinaryDataDecoder.read_uint16be(self.event_data, pos + 0x00) & 0x03FF
            isig = BinaryDataDecoder.read_uint16be(self.event_data, pos + 0x02) / 100.0

            # TODO Fixme "vctr" ???
            # vctr = NumberHelper.make32BitIntFromNBitSignedInt((((payload_decoded[0] >> 0x02) & 0x03) << 8) | payload_decoded[3], 10) / 100.0
            # vctrraw = NumberHelper.make32BitIntFromNBitSignedInt((((payload_decoded[0] >> 0x02) & 0x03) << 8) | payload_decoded[4] & 0x000000FF)
            # vctrraw = (((payload_decoded[0] >> 0x02) & 0x03) << 8) | payload_decoded[3] & 0x000000FF
            vctrraw = (((self.event_data[pos] >> 2 & 3) << 8) | self.event_data[pos + 4] & 0x000000FF)
            if ((vctrraw & 0x0200) != 0):
                vctrraw |= 0xFFFFFE00
                # vctrraw = vctrraw & 0xFFFFFE00
            vctr = vctrraw / 100.0

            rate_of_change = float( struct.unpack( '>h', self.event_data[(pos + 0x05) : (pos + 0x07)] )[0] ) / 100
            sensor_status = BinaryDataDecoder.read_byte(self.event_data, 0x07)
            reading_status = BinaryDataDecoder.read_byte(self.event_data, 0x08)

            backfilled_data = (reading_status & 1) == 1
            settings_changed = (reading_status & 2) == 2
            noisy_data = sensor_status == 1
            discard_data = sensor_status == 2
            sensor_error = sensor_status == 3

            sensor_exception = 0x0300
            if sg >= 0x0300:
                sensor_exception = sg
                sg = 0

            sensor_exception_text = NGPConstants.SENSOR_EXCEPTIONS_NAME[sensor_exception]

            yield SensorGlucoseReading(event_data = self.event_data,
                                       timestamp = timestamp,
                                       dynamic_action_requestor = self.dynamic_action_requestor,
                                       sg = sg,
                                       predicted_sg = self.predicted_sg,
                                       noisy_data = noisy_data,
                                       discard_data = discard_data,
                                       sensor_error = sensor_error,
                                       backfilled_data = backfilled_data,
                                       settings_changed = settings_changed,
                                       isig = isig,
                                       rate_of_change = rate_of_change,
                                       vctr = vctr,
                                       sensor_exception_text = sensor_exception_text
                                       )
            pos = pos +9

class SensorGlucoseReading(NGPHistoryEvent):
    def __init__(self, event_data, timestamp, dynamic_action_requestor, sg, predicted_sg=0, isig=0, vctr=0, rate_of_change=0.0,
                 backfilled_data=False, settings_changed=False, noisy_data=False, discard_data=False, sensor_error=False,
                 sensor_exception_text=""):
        super().__init__(event_data)
        self.eventData = event_data
        self._timestamp = timestamp
        self._dynamicActionRequestor = dynamic_action_requestor
        self.sg = sg
        self.predictedSg = predicted_sg
        self.isig = isig
        self.vctr = vctr
        self.rateOfChange = rate_of_change
        self.backfilledData = backfilled_data
        self.settingsChanged = settings_changed
        self.noisyData = noisy_data
        self.discardData = discard_data
        self.sensorError = sensor_error
        self.sensorExceptionText = sensor_exception_text

    def __str__(self):
        return ("{0} SG:{1} ({9}), predictedSg:{2}, "
                "isig:{6}, rateOfChange:{7}, "
                "noisyData:{3}, discardData: {4}, sensorError:{5}, sensorExceptionText: '{8}'").format(
            NGPHistoryEvent.__shortstr__(self),
            self.sg,
            self.predictedSg,
            self.noisyData,
            self.discardData,
            self.sensorError,
            self.isig,
            self.rateOfChange,
            self.sensorExceptionText,
            round(self.sg / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),
        )

    @property
    def source(self):
        return self._dynamicActionRequestor

    @property
    def dynamic_action_requestor(self):
        return self._dynamicActionRequestor

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def size(self):
        return 0

    @property
    def event_type(self):
        return NGPHistoryEvent.EVENT_TYPE.GENERATED_SENSOR_GLUCOSE_READINGS_EXTENDED_ITEM

    def event_instance(self):
        return self

class BolusWizardEstimateEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)
        self.programmed = False

    def __str__(self):
        return ("{0} "
                "BG Input:{1}, "
                "Carbs:{2}, "
                "Food est.:{3}, "
                "Carb ratio: {4}, "
                "Correction est.:{5}, "
                "Wizard est.: {6}, "
                "User modif.: {7}, "
                "Final est.: {8}, "
                "Active insulin (iob):{9}, "
                "Active insulin corr.:{10}, "
                "Programmed: {11}, "
                "lowBgTarget: {12}, "
                "highBgTarget: {13}, "
                "bgUnits: '{14}' ({17}), "
                "carbUnits: '{15}' ({18}), "
                "bolusStepSizeName: '{16}' ({20}), "
                "isf: {19}"
                ).format(NGPHistoryEvent.__shortstr__(self),  # 0
                         self.bg_input,  # 1
                         self.carb_input,  #2
                         self.food_estimate,  #3
                         self.carb_ratio,  # 4
                         self.correction_estimate,  # 5
                         self.bolus_wizard_estimate,  # 6
                         self.estimate_modified_by_user,  # 7
                         self.final_estimate,  # 8
                         self.active_insulin,  # 9
                         self.active_insulin_correction,  # 10
                         self.programmed,  # 11
                         self.low_bg_target,  # 12
                         self.high_bg_target,  # 13
                         self.bg_units_name,  # 14
                         self.carb_units_name,  # 15
                         self.bolus_step_size_name,  # 16
                         self.bg_units,  # 17
                         self.carb_units,  # 18
                         self.isf,  # 19
                         self.bolus_step_size,  # 20
                         )

    @property
    def bg_units(self):
        # See NGPUtil.NGPConstants.BG_UNITS
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)  # bgUnits

    @property
    def bg_units_name(self):
        # See NGPUtil.NGPConstants.BG_UNITS
        return NGPConstants.BG_UNITS_NAME[self.bg_units]

    @property
    def carb_units(self):
        # See NGPUtil.NGPConstants.CARB_UNITS
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)  # carbUnits

    @property
    def carb_units_name(self):
        return NGPConstants.CARB_UNITS_NAME[self.carb_units]

    @property
    def bg_input(self):
        bg_input = BinaryDataDecoder.read_uint16be(self.event_data, 0x0D)  # bgInput
        return bg_input if self.bg_units == NGPConstants.BG_UNITS.MG_DL else bg_input / 10.0

    @property
    def carb_input(self):
        carbs = BinaryDataDecoder.read_uint16be(self.event_data, 0x0F)  # carbInput
        return carbs if self.carb_units == NGPConstants.CARB_UNITS.GRAMS else carbs / 10.0

    @property
    def isf(self):
        isf = BinaryDataDecoder.read_uint16be(self.event_data, 0x11)  # isf
        return isf if self.bg_units == NGPConstants.BG_UNITS.MG_DL else isf / 10.0

    @property
    def carb_ratio(self):
        carb_ratio = BinaryDataDecoder.read_uint32be(self.event_data, 0x13)  # carbRatio
        return carb_ratio / 10.0 if (self.carb_units == NGPConstants.CARB_UNITS.GRAMS) else carb_ratio / 1000.0

    @property
    def low_bg_target(self):
        bg_target = BinaryDataDecoder.read_uint16be(self.event_data, 0x17)  # lowBgTarget
        return bg_target if self.bg_units == NGPConstants.BG_UNITS.MG_DL else bg_target / 10.0

    @property
    def high_bg_target(self):
        bg_target = BinaryDataDecoder.read_uint16be(self.event_data, 0x19) # highBgTarget
        return bg_target if self.bg_units == NGPConstants.BG_UNITS.MG_DL else bg_target / 10.0

    @property
    def correction_estimate(self):  # correctionEstimate
        return ((BinaryDataDecoder.read_byte(self.event_data, 0x1B) << 8) |
                (BinaryDataDecoder.read_byte(self.event_data, 0x1C) << 8) |
                (BinaryDataDecoder.read_byte(self.event_data, 0x1D) << 8) |
                BinaryDataDecoder.read_byte(self.event_data, 0x1E)) / 10000.0

    @property
    def food_estimate(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x1F) / 10000.0 # foodEstimate

    @property
    def active_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x23) / 10000.0 # iob

    @property
    def active_insulin_correction(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x27) / 10000.0 # iobAdjustment

    @property
    def bolus_wizard_estimate(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x2B) / 10000.0 # bolusWizardEstimate

    @property
    def bolus_step_size(self):
        # See NGPUtil.NGPConstants.BOLUS_STEP_SIZE
        return BinaryDataDecoder.read_byte(self.event_data, 0x2F)  # bolusStepSize

    @property
    def bolus_step_size_name(self):
        # See NGPUtil.NGPConstants.BOLUS_STEP_SIZE
        return NGPConstants.BOLUS_STEP_SIZE_NAME[self.bolus_step_size]

    @property
    def estimate_modified_by_user(self):
        return (BinaryDataDecoder.read_uint32be(self.event_data, 0x30) & 0x01) == 0x01 # estimateModifiedByUser

    @property
    def final_estimate(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x31) / 10000.0 # finalEstimate

class BasalSegmentStartEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return "{0} Basal Rate:{1}, Pattern#:{4} ({2}), Segment#:{3}".format(NGPHistoryEvent.__shortstr__(self),
                                                                             self.rate,
                                                                             self.pattern_number,
                                                                             self.segment_number,
                                                                             self.pattern_name)

    @property
    def rate(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x0D) / 10000.0

    @property
    def pattern_number(self):
        # See NGPUtil.NGPConstants.CARB_UNITS
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def segment_number(self):
        # See NGPUtil.NGPConstants.CARB_UNITS
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)  # return this.eventData[0x0C]

    @property
    def pattern_name(self):
        return NGPConstants.BASAL_PATTERN_NAME[self.pattern_number]

class InsulinDeliveryStoppedEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Reason: {2} ({1})'.format(NGPHistoryEvent.__shortstr__(self),
                                              self.suspend_reason,
                                              self.suspend_reason_text)

    @property
    def suspend_reason(self):
        # See NGPUtil.NGPConstants.SUSPEND_REASON
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def suspend_reason_text(self):
        # See NGPUtil.NGPConstants.SUSPEND_REASON
        return NGPConstants.SUSPEND_REASON_NAME[self.suspend_reason]

class InsulinDeliveryRestartedEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Reason: {2} ({1})'.format(NGPHistoryEvent.__shortstr__(self),
                                              self.resume_reason,
                                              self.resume_reason_text)

    @property
    def resume_reason(self):
        # See See NGPUtil.NGPConstants.RESUME_REASON
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def resume_reason_text(self):
        # See NGPUtil.NGPConstants.SUSPEND_REASON
        return NGPConstants.RESUME_REASON_NAME[self.resume_reason]

class PLGMControllerStateEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0}'.format(NGPHistoryEvent.__str__(self))

class CalibrationCompleteEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0} calFactor:{1}, bgTarget:{2} ({3})'.format(NGPHistoryEvent.__shortstr__(self),
                                                          self.cal_factor,
                                                          self.bg_target, self.bg_target_mmol)

    @property
    def cal_factor(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0B) / 100

    @property
    def bg_target(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0D)

    @property
    def bg_target_mmol(self):
        return round(self.bg_target / NGPConstants.BG_UNITS.MMOLXLFACTOR,1)

class PumpEvent():
    def __init__(self, code,data):
        self.code = code
        self.data = data
        self.type = None
        self.priority = None
        self.insulin = None
        self.time = None
        self.list = None
        self.bg = None
        self.string = None

    # Alarms:
    # #103 alarmData: HM-------- HM=Hours(hour,min)
    # #105 alarmData: UUUU------ U=Insulin(div 10000)
    # #108 alarmData: HMR------- HM=Clock(hour,min) R=Personal Reminder(1/2/3/4/5/6/7=BG Check/8=Medication)
    # #109 alarmData: X--------- X=Days (days since last set change)
    # #802 alarmData: XSS-HMSS-- X=Snooze(mins) S=SGV(mgdl) HM=Clock(hour,min)
    # #805 alarmData: XSS-HMSS-- X=Snooze(mins) S=SGV(mgdl) HM=Clock(hour,min)
    # #816 alarmData: XSS------- X=Snooze(mins) S=SGV(mgdl)
    # #817 alarmData: XSS------- X=Before(mins) S=SGV(mgdl)
    # #869 alarmData: HM-------- HM=Clock(hour,min)

    def alarm_string(self):
        code = self.code
        data = self.data
        self.string = NGPConstants.ALARM_MESSAGE_NAME[code]

        if code == 3:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 4:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 6:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 7:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 8:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 11:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 15:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 23:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 53:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 54:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 58:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 61:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.LOWEST
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 66:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.LOWEST
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 70:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 71:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            insulin = self.get_insulin(0, data)
            self.insulin = insulin
            return self.format(self.type, self.priority,(NGPConstants.ALARM_MESSAGE_NAME[code]).format(insulin))

        if code == 72:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            insulin = self.get_insulin(0, data)
            self.insulin = insulin
            return self.format(self.type, self.priority,(NGPConstants.ALARM_MESSAGE_NAME[code]).format(insulin))

        if code == 73:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 84:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 100:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 104:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 105:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            insulin = self.get_insulin(0, data)
            self.insulin = insulin
            return self.format(self.type, self.priority,(NGPConstants.ALARM_MESSAGE_NAME[code]).format(insulin))

        # TODO Fix me, add "hours"
        # if code == 106:
        #     self.type = NGPConstants.ALARM_TYPE.PUMP
        #     self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
        #     return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 107:
            self.type = NGPConstants.ALARM_TYPE.REMINDER
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 108:
            self.type = NGPConstants.ALARM_TYPE.REMINDER
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL

            str_list = self.get_list(2, data, NGPConstants.ALARM_PERSONAL_REMINDER)
            time = self.get_clock(0,data)
            # TODO Add time to output (self.time)
            self.time = time
            self.list = str_list
            return self.format(self.type, self.priority,(NGPConstants.ALARM_MESSAGE_NAME[code]).
                               format(str_list, time))

        if code == 109:
            self.type = NGPConstants.ALARM_TYPE.REMINDER
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            str_list = self.get_list(0,data, "One day|Two days|Three days")
            self.list = str_list
            return self.format(self.type, self.priority,(NGPConstants.ALARM_MESSAGE_NAME[code]).
                               format(str_list))

        if code == 110:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOWEST
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 113:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 117:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 775:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 776:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 777:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 778:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 780:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 781:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 784:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 788:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 790:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 791:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 794:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 795:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 796:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 797:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOWEST
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 798:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOWEST
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 799:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOWEST
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 801:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])


        if code == 802:
            bg = self.get_glucose(0x01,data)
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            if bg < 0x300:
                self.bg = bg
                return self.format(self.type, self.priority, (NGPConstants.ALARM_MESSAGE_NAME[code]).
                                   format(bg, round(bg/NGPConstants.BG_UNITS.MMOLXLFACTOR,1)))
            else:
                return "[Error data]"

        if code == 803:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 805:
            bg = self.get_glucose(0x01,data)
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            if bg < 0x300:
                self.bg = bg
                return self.format(self.type, self.priority, (NGPConstants.ALARM_MESSAGE_NAME[code]).
                                   format(bg, round(bg/NGPConstants.BG_UNITS.MMOLXLFACTOR,1)))
            else:
                return "[Error data]"

        if code == 806:
            self.type = NGPConstants.ALARM_TYPE.SMARTGUARD
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 807:
            self.type = NGPConstants.ALARM_TYPE.SMARTGUARD
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            time = self.get_clock(4,data)
            # TODO Add time to output (self.time)
            self.time = time
            return self.format(self.type, self.priority,(NGPConstants.ALARM_MESSAGE_NAME[code]).format(time))

        if code == 808:
            self.type = NGPConstants.ALARM_TYPE.SMARTGUARD
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 809:
            bg = self.get_glucose(0x01,data)
            self.type = NGPConstants.ALARM_TYPE.SMARTGUARD
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            if bg < 0x300:
                self.bg = bg
                return self.format(self.type, self.priority, (NGPConstants.ALARM_MESSAGE_NAME[code]).
                                   format(bg, round(bg/NGPConstants.BG_UNITS.MMOLXLFACTOR,1)))
            else:
                return "[Error data]"

        if code == 810:
            self.type = NGPConstants.ALARM_TYPE.SMARTGUARD
            self.priority = NGPConstants.ALARM_PRIORITY.LOW
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 811:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 812:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 814:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 815:
            self.type = NGPConstants.ALARM_TYPE.PUMP
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            return self.format(self.type, self.priority, NGPConstants.ALARM_MESSAGE_NAME[code])

        if code == 816:
            bg = self.get_glucose(0x01,data)
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.EMERGENCY
            if bg < 0x300:
                self.bg = bg
                return self.format(self.type, self.priority, (NGPConstants.ALARM_MESSAGE_NAME[code]).
                                   format(bg, round(bg/NGPConstants.BG_UNITS.MMOLXLFACTOR,1)))
            else:
                return "[Error data]"

        if code == 817:
            bg = self.get_glucose(0x01,data)
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.HIGH
            if bg:
                self.bg = bg
                return self.format(self.type, self.priority, (NGPConstants.ALARM_MESSAGE_NAME[code]).
                                   format(bg, round(bg/NGPConstants.BG_UNITS.MMOLXLFACTOR,1)))
            else:
                return "[Error data]"

        if code == 869:
            self.type = NGPConstants.ALARM_TYPE.REMINDER
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL

            # TODO
            time = self.get_clock(0,data)
            self.time = time
            return self.format(self.type, self.priority,(NGPConstants.ALARM_MESSAGE_NAME[code]).format(time))

        if code == 870:
            self.type = NGPConstants.ALARM_TYPE.SENSOR
            self.priority = NGPConstants.ALARM_PRIORITY.NORMAL
            return self.format(self.type, self.priority,NGPConstants.ALARM_MESSAGE_NAME[code])

        else:
            return ("[Don't parse data]: {0}").format(binascii.hexlify(data))

    def get_glucose(self, offset,data):
        bg = BinaryDataDecoder.read_uint16be(data, offset)
        if bg < 0x300:
            return bg
        else:
            return False

    def get_list(self,offset, data, list_str):
        index = BinaryDataDecoder.read_byte(data, offset) - 1
        list = list_str.split("|")
        if index > 0 and index <= len(list):
            return list[index]
        else:
            return "~"

    def get_clock(self,offset,data):
        hour_in_minutes = (BinaryDataDecoder.read_byte(data, offset) & 0xFF ) * 60
        minutes = BinaryDataDecoder.read_byte(data, offset + 0x01) & 0xFF
        minutes = minutes + hour_in_minutes
        time = str(timedelta(minutes=minutes))
        return time

    def get_insulin(self, offset, data):
        return  BinaryDataDecoder.read_uint32be(data, offset) / 10000.0

    def format(self, type, priority, str):
        string = NGPConstants.ALARM_TYPE_NAME[type] + ", " + NGPConstants.ALARM_PRIORITY_NAME[priority] + ": "
        msg = str.split("|")
        string = string + msg[0]
        if len(msg) >=2 :
            string = string + "|" + msg[1]
        return string

class AlarmNotificationEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0}, Code:{1}, Mode:{2} Extra:{3} History:{4} String:{5}'.format(NGPHistoryEvent.__shortstr__(self),
                                                                                      self.fault_number,
                                                                                      self.notification_mode,
                                                                                      self.extra_data,
                                                                                      self.alarm_history,
                                                                                      self.alarm_string)

    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    @property
    def fault_number(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0B)

    @property
    def notification_mode(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x11)

    @property
    def extra_data(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x12) & 2) == 2

    @property
    def alarm_history(self):
        return (BinaryDataDecoder.read_byte(self.event_data, 0x12) & 4) == 4

    @property
    def alarm_data(self):
        return self.event_data[0x13:0x1D]

    @property
    def alarm_string(self):
        alarm = PumpEvent(self.fault_number, self.alarm_data)
        alarm_str = alarm.alarm_string()

        self.type = alarm.type
        self.priority = alarm.priority
        self.insulin = alarm.insulin
        self.time = alarm.time
        self.list = alarm.list
        self.bg = alarm.bg
        self.string = alarm.string

        return alarm_str

class AlarmClearedEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0}, String: Cleared Event code:{1}'.format(NGPHistoryEvent.__shortstr__(self), self.fault_number)

    @property
    def fault_number(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0B)

class SensorAlertSilenceStartedEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0}'.format(NGPHistoryEvent.__str__(self))

class SensorAlertSilenceEndedEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0}'.format(NGPHistoryEvent.__str__(self))

class CalibrationReminderChangeEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return "{0} OldStatus: {1}({2}), NewStatus: {3}({4}), OldMinutes: {5}, NewMinutes: {6}".format(
            NGPHistoryEvent.__shortstr__(self), self.old_status_name, self.old_status, self.new_status_name, self.new_status,
            self.old_minutes, self.new_minutes)

    @property
    def old_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0C)

    @property
    def new_status(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x12)

    @property
    def old_status_name(self):
        return "On" if self.old_status == 1 else "Off"
    @property
    def new_status_name(self):
        return "On" if self.new_status == 1 else "Off"

    @property
    def old_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x0D)

    @property
    def new_minutes(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x13)

class DailyTotalsEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)
    # EventType.DAILY_TOTALS
    # !!!!! Shift 0x0B (Header) !!!!!
    # Data:
    #      ?0 ?1 ?2 ?3 ?4 ?5 ?6 ?7 ?8 ?9 ?A ?B ?C ?D ?E ?F
    # 0x00 CR CR CR CR CO CO CO CO CD CD BG BA BA BL BL BH
    # 0x10 BH MG MA MA ML ML MH MH BV BV TD TD TD TD TB TB
    # 0x20 TB TB PB TI TI TI TI PI WW WA WA WB WC WC WC WC
    # 0x30 WD WD WD WD WE WE WE WE WF WF WF WF WG WH WI WJ
    # 0x40 ST ST SA SA SD SD SX SX SH SY SY SI SZ SZ SL SK
    # 0x50 SK AA AA AB AB AC AC AD AD AE AE AF AF AG AG AH
    # 0x60 AH
    #
    # CR = RTC
    # CO - OFFSET
    # CD = DURATION (mins)
    #
    # BG = METER_BG_COUNT
    # BA = METER_BG_AVERAGE (mg/dL)
    # BL = LOW_METER_BG (mg/dL)
    # BH = HIGH_METER_BG (mg/dL)
    # MG = MANUALLY_ENTERED_BG_COUNT
    # MA = MANUALLY_ENTERED_BG_AVERAGE (mg/dL)
    # ML = LOW_MANUALLY_ENTERED_BG (mg/dL)
    # MH = HIGH_MANUALLY_ENTERED_BG (mg/dL)
    # BV = BG_AVERAGE (mg/dL)
    #
    # TD = TOTAL_INSULIN (div 10000)
    # TB = BASAL_INSULIN (div 10000)
    # PB = BASAL_PERCENT
    # TI = BOLUS_INSULIN (div 10000)
    # PI = BOLUS_PERCENT
    #
    # WW = CARB_UNITS
    # WA = TOTAL_FOOD_INPUT
    # WB = BOLUS_WIZARD_USAGE_COUNT
    # WC = TOTAL_BOLUS_WIZARD_INSULIN_AS_FOOD_ONLY_BOLUS (div 10000)
    # WD = TOTAL_BOLUS_WIZARD_INSULIN_AS_CORRECTION_ONLY_BOLUS (div 10000)
    # WE = TOTAL_BOLUS_WIZARD_INSULIN_AS_FOOD_AND_CORRECTION (div 10000)
    # WF = TOTAL_MANUAL_BOLUS_INSULIN (div 10000)
    # WG = BOLUS_WIZARD_FOOD_ONLY_BOLUS_COUNT
    # WH = BOLUS_WIZARD_CORRECTION_ONLY_BOLUS_COUNT
    # WI = BOLUS_WIZARD_FOOD_AND_CORRECTION_BOLUS_COUNT
    # WJ = MANUAL_BOLUS_COUNT
    #
    # ST = SG_COUNT
    # SA = SG_AVERAGE (mg/dL)
    # SD = SG_STDDEV (mg/dL)
    # SX = SG_DURATION_ABOVE_HIGH (mins)
    # SH = PERCENT_ABOVE_HIGH
    # SX = SG_DURATION_WITHIN_LIMIT (mins)
    # SI = PERCENT_WITHIN_LIMIT
    # SZ = SG_DURATION_BELOW_LOW (mins)
    # SL = PERCENT_BELOW_LOW
    # SK = LGS_SUSPENSION_DURATION (mins)
    #
    # AA = HIGH_PREDICTIVE_ALERTS
    # AB = LOW_PREDICTIVE_ALERTS
    # AC = LOW_BG_ALERTS
    # AD = HIGH_BG_ALERTS
    # AE = RISING_RATE_ALERTS
    # AF = FALLING_RATE_ALERTS
    # AG = LOW_GLUCOSE_SUSPEND_ALERTS
    # AH = PREDICTIVE_LOW_GLUCOSE_SUSPEND_ALERTS

    def __str__(self):
        return ("{0}, "
                "Date:{1}, Duration:{2}, "
                "TDD:{3}, Basal:{4} ({5}%), Bolus:{6} ({7}%), "
                "BG: Count:{8}, Average:{9} ({10}), "
                "Meter: Count:{11}, Average:{12} ({13}), Low:{14} ({15}), High:{16} ({17}), "
                "Manual: Count:{18}, Average:{19} ({20}), Low:{21} ({22}), High:{23} ({24}), "
                "SG: Count:{25}, Average:{26} ({27}), StdDev:{28} ({29}), High:{30}% ({31} Minutes), InRange:{32}% ({33} Minutes), Low:{34}% ({35} Minutes), Suspended:{36}, "
                "Alert: BeforeHigh:{37}, BeforeLow:{38}, Low:{39}, High:{40}, Rise:{41}, Fall:{42}, LGS:{43}, PLGS:{44}, "
                "Wizard: Count:{45}, Units:{46} ({47}), FoodInput:{48}, Food:{49} ({50}), Correction:{51} ({52}), Food+Cor:{53} ({54}), Manual:{55} ({56})"
                ).format(NGPHistoryEvent.__shortstr__(self),
                         # Date
                         self.date, self.duration,
                         # TDD
                         self.total_insulin, self.basal_insulin, self.basal_percent, self.bolus_insulin, self.bolus_percent,

                         # BG
                         self.meter_bg_count + self.manually_entered_bg_count, self.bg_average,
                         round(self.bg_average / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),

                         # Meter
                         self.meter_bg_count, self.meter_bg_average,
                         round(self.meter_bg_average / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1), self.low_meter_bg,
                         round(self.low_meter_bg / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1), self.high_meter_bg,
                         round(self.high_meter_bg / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),

                         # Manual
                         self.manually_entered_bg_count, self.manually_entered_bg_average,
                         round(self.manually_entered_bg_average / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),
                         self.low_manually_entered_bg,
                         round(self.low_manually_entered_bg / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),
                         self.high_manually_entered_bg,
                         round(self.high_manually_entered_bg / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),

                         # SG
                         self.sg_count, self.sg_average, round(self.sg_average / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),
                         self.sg_stddev, round(self.sg_stddev / NGPConstants.BG_UNITS.MMOLXLFACTOR, 1),
                         self.percent_above_high, self.sg_duration_above_high, self.percent_within_limit,
                         self.sg_duration_within_limit, self.percent_below_low, self.sg_duration_below_low, self.lgs_suspension_duration,

                         # Alert
                         self.high_predictive_alerts, self.low_predictive_alerts, self.low_bg_alerts, self.high_bg_alerts, self.rising_rate_alerts,
                         self.falling_rate_alerts, self.low_glucose_suspend_alerts, self.predictive_low_glucose_suspend_alerts,

                         # Wizard
                         self.bolus_wizard_usage_count, self.carb_units, self.carb_units_name, self.total_food_input,
                         self.total_bolus_wizard_insulin_as_food_only_bolus, self.bolus_wizard_food_only_bolus_count,
                         self.total_bolus_wizard_insulin_as_correction_only_bolus, self.bolus_wizard_correction_only_bolus_count,
                         self.total_bolus_wizard_insulin_as_food_and_correction, self.bolus_wizard_food_and_correction_bolus_count,
                         self.total_manual_bolus_insulin, self.manual_bolus_count


                         )

    @property
    def encoded_datetime(self):
        return BinaryDataDecoder.read_uint64be(self.event_data, 0x0B)

    @property
    def date(self):
        date_time_data = self.encoded_datetime
        return DateTimeHelper.decode_date_time(date_time_data)

    @property
    def offset(self):
        date_time_data = self.encoded_datetime
        return DateTimeHelper.decode_date_time_offset(date_time_data)

    @property
    def duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x13)

    @property
    def meter_bg_count(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x15)

    @property
    def meter_bg_average(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x16)

    @property
    def low_meter_bg(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x18)

    @property
    def high_meter_bg(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x1A)

    @property
    def manually_entered_bg_count(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x1C)

    @property
    def manually_entered_bg_average(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x1D)

    @property
    def low_manually_entered_bg(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x1F)

    @property
    def high_manually_entered_bg(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x21)

    @property
    def bg_average(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x23)

    @property
    def total_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x25) / 10000.0

    @property
    def basal_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x29) / 10000.0

    @property
    def basal_percent(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x2D)

    @property
    def bolus_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x2E) / 10000.0

    @property
    def bolus_percent(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x32)

    @property
    def carb_units(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x33)

    @property
    def carb_units_name(self):
        # See NGPUtil.NGPConstants.CARB_UNITS
        return NGPConstants.CARB_UNITS_NAME[self.carb_units]

    @property
    def total_food_input(self):
        total_food_input = BinaryDataDecoder.read_uint16be(self.event_data, 0x34)
        return total_food_input if self.carb_units == NGPConstants.CARB_UNITS.GRAMS else total_food_input / 10.0

    @property
    def bolus_wizard_usage_count(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x36)

    @property
    def total_bolus_wizard_insulin_as_food_only_bolus(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x37) / 10000.0

    @property
    def total_bolus_wizard_insulin_as_correction_only_bolus(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x3B) / 10000.0

    @property
    def total_bolus_wizard_insulin_as_food_and_correction(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x3F) / 10000.0

    @property
    def total_manual_bolus_insulin(self):
        return BinaryDataDecoder.read_uint32be(self.event_data, 0x43) / 10000.0

    @property
    def bolus_wizard_food_only_bolus_count(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x47)

    @property
    def bolus_wizard_correction_only_bolus_count(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x48)

    @property
    def bolus_wizard_food_and_correction_bolus_count(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x49)

    @property
    def manual_bolus_count(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x4A)

    @property
    def sg_count(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x4B)

    @property
    def sg_average(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x4D)

    @property
    def sg_stddev(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x4F)

    @property
    def sg_duration_above_high(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x51)

    @property
    def percent_above_high(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x53)

    @property
    def sg_duration_within_limit(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x54)

    @property
    def percent_within_limit(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x56)

    @property
    def sg_duration_below_low(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x57)

    @property
    def percent_below_low(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x59)

    @property
    def lgs_suspension_duration(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x5A)

    @property
    def high_predictive_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x5C)

    @property
    def low_predictive_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x5E)

    @property
    def low_bg_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x60)

    @property
    def high_bg_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x62)

    @property
    def rising_rate_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x64)

    @property
    def falling_rate_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x66)

    @property
    def low_glucose_suspend_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x68)

    @property
    def predictive_low_glucose_suspend_alerts(self):
        return BinaryDataDecoder.read_uint16be(self.event_data, 0x6A)

class SourceIdConfigurationEvent(NGPHistoryEvent):
    def __init__(self, event_data):
        NGPHistoryEvent.__init__(self, event_data)

    def __str__(self):
        return '{0} Count:{1}, DeviceList:{2}'.format(NGPHistoryEvent.__shortstr__(self), self.number_of_segments, self.device_list)

    @property
    def number_of_segments(self):
        return BinaryDataDecoder.read_byte(self.event_data, 0x0B)

    @property
    def device_list(self):
        segments = {}
        pos = 0x0C
        for i in range(self.number_of_segments):
            number = BinaryDataDecoder.read_byte(self.event_data, pos)
            sn = (self.event_data[pos + 0x01: pos + 0x0B]).decode('utf-8')[::-1]
            device = self.event_data[pos + 0x13: pos + 0x1B]
            ver_major = BinaryDataDecoder.read_byte(self.event_data, pos + 0x1B)
            ver_minor = BinaryDataDecoder.read_byte(self.event_data, pos + 0x1C)
            revision = (self.event_data[pos + 0x1D: pos + 0x1E])

            if revision[0] == 0:
                revision = ""
            else:
                revision = revision.decode('utf-8')

            ver_str = ("{0:0d}.{1:0d}{2}").format(ver_major,ver_minor,revision)

            if device[0] == 0:
                device = ""
            else:
                device = device.decode('utf-8')[::-1]
            seg = {
                "list_number" : number,
                "device" : device,
                "sn" : sn,
                "ver_major" : ver_major,
                "ver_minor" : ver_minor,
                "revision" : revision,
                "ver_str" : ver_str,
            }
            segments.update({"{0}".format(i+1) : seg })
            pos = pos + 0x1E
        return segments

class StartOfDayMarkerEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0}'.format(NGPHistoryEvent.__shortstr__(self))

class EndOfDayMarkerEvent(NGPHistoryEvent):
    def __str__(self):
        return '{0}'.format(NGPHistoryEvent.__shortstr__(self))

################# HISTORY ######################

asciiKey= {
    'STX' : 0x02,
    'ETX' : 0x03,
    'EOT' : 0x04,
    'ENQ' : 0x05,
    'ACK' : 0x06,
    'LF'  : 0x0A,
    'CR'  : 0x0D,
    'NAK' : 0x15,
    'ETB' : 0x17
}

def ord_hack(char_or_byte):
    return char_or_byte if isinstance(char_or_byte, int) else ord(char_or_byte)

class CommandType:
    NO_TYPE = 0x0
    OPEN_CONNECTION = 0x10
    CLOSE_CONNECTION = 0x11
    SEND_MESSAGE = 0x12
    READ_INFO = 0x14
    REQUEST_LINK_KEY = 0x16
    SEND_LINK_KEY = 0x17
    RECEIVE_MESSAGE = 0x80
    SEND_MESSAGE_RESPONSE = 0x81
    REQUEST_LINK_KEY_RESPONSE = 0x86

class CommandAction:
    NO_TYPE = 0x0
    INITIALIZE = 0x01
    SCAN_NETWORK = 0x02
    JOIN_NETWORK = 0x03
    LEAVE_NETWORK = 0x04
    TRANSMIT_PACKET = 0x05
    READ_DATA = 0x06
    READ_STATUS = 0x07
    READ_NETWORK_STATUS = 0x08
    SET_SECURITY_MODE = 0x0C
    READ_STATISTICS = 0x0D
    SET_RF_MODE = 0x0E
    CLEAR_STATUS = 0x10
    SET_LINK_KEY = 0x14

class ComDCommand:
    HIGH_SPEED_MODE_COMMAND = 0x0412
    TIME_REQUEST = 0x0403
    TIME_RESPONSE = 0x0407
    READ_PUMP_STATUS_REQUEST = 0x0112
    READ_PUMP_STATUS_RESPONSE = 0x013C
    READ_BASAL_PATTERN_REQUEST = 0x0116
    READ_BASAL_PATTERN_RESPONSE = 0x0123
    READ_BOLUS_WIZARD_CARB_RATIOS_REQUEST = 0x012B
    READ_BOLUS_WIZARD_CARB_RATIOS_RESPONSE = 0x012C
    READ_BOLUS_WIZARD_SENSITIVITY_FACTORS_REQUEST = 0x012E
    READ_BOLUS_WIZARD_SENSITIVITY_FACTORS_RESPONSE = 0x012F
    READ_BOLUS_WIZARD_BG_TARGETS_REQUEST = 0x0131
    READ_BOLUS_WIZARD_BG_TARGETS_RESPONSE = 0x0132
    DEVICE_STRING_REQUEST = 0x013A
    DEVICE_STRING_RESPONSE = 0x013B
    DEVICE_CHARACTERISTICS_REQUEST = 0x0200
    DEVICE_CHARACTERISTICS_RESPONSE = 0x0201
    READ_HISTORY_REQUEST = 0x0304
    READ_HISTORY_RESPONSE = 0x0305
    END_HISTORY_TRANSMISSION = 0x030A
    READ_HISTORY_INFO_REQUEST = 0x030C
    READ_HISTORY_INFO_RESPONSE = 0x030D
    UNMERGED_HISTORY_RESPONSE = 0x030E
    INITIATE_MULTIPACKET_TRANSFER = 0xFF00
    MULTIPACKET_SEGMENT_TRANSMISSION = 0xFF01
    MULTIPACKET_RESEND_PACKETS = 0xFF02
    ACK_MULTIPACKET_COMMAND = 0x00FE
    NAK_COMMAND = 0x00FF
    BOLUSES_REQUEST = 0x0114
    REMOTE_BOLUS_REQUEST = 0x0100
    REQUEST_0x0124 = 0x0124
    REQUEST_0x0405 = 0x0405
    TEMP_BASAL_REQUEST = 0x0115
    SUSPEND_RESUME_REQUEST = 0x0107
    NGP_PARAMETER_REQUEST = 0x0138

class HistoryDataType:
    PUMP_DATA = 0x02
    SENSOR_DATA = 0x03

class HistoryRangeType:
    FULL_HISTORY = 0x03
    PARTIAL_HISTORY = 0x04

class TimeoutException( Exception ):
    pass

class UnexpectedMessageException( Exception ):
    pass

class ChecksumException( Exception ):
    pass

class NegotiationException( Exception ):
    pass

class InvalidMessageError( Exception ):
    pass

class DateTimeHelper(object):
    # Base time is midnight 1st Jan 2000 (UTC)
    baseTime = 946684800
    epoch = datetime.datetime.utcfromtimestamp(0)

    @staticmethod
    def decode_date_time_offset(pump_date_time):
        return (pump_date_time & 0xffffffff) - 0x100000000

    @staticmethod
    def decode_date_time(pump_date_time, offset=None):
        if offset == None:
            rtc = (pump_date_time >> 32) & 0xffffffff
            offset = DateTimeHelper.decode_date_time_offset(pump_date_time)
        else:
            rtc = pump_date_time

        # The time from the pump represents epoch_time in UTC, but we treat it as if it were in our own timezone
        # We do this, because the pump does not have a concept of timezone
        # For example, if baseTime + rtc + offset was 1463137668, this would be
        # Fri, 13 May 2016 21:07:48 UTC.
        # However, the time the pump *means* is Fri, 13 May 2016 21:07:48 in our own timezone
        offset_from_utc = (datetime.datetime.utcnow() - datetime.datetime.now()).total_seconds()
        epoch_time = DateTimeHelper.baseTime + rtc + offset + offset_from_utc
        if epoch_time < 0:
            epoch_time = 0

        # print ' ### DateTimeHelper.decodeDateTime rtc:0x{0:x} {0} offset:0x{1:x} {1} epoch_time:0x{2:x} {2}'.format(rtc, offset, epoch_time)

        # Return a non-naive datetime in the local timezone
        # (so that we can convert to UTC for Nightscout later)
        local_tz = tz.tzlocal()
        result = datetime.datetime.fromtimestamp(epoch_time, local_tz)
        # print ' ### DateTimeHelper.decodeDateTime {0:x} {1}'.format(pumpDateTime, result)
        return result

    @staticmethod
    def rtc_from_date(user_date, offset):
        epoch_time = int((user_date - DateTimeHelper.epoch).total_seconds())
        rtc = epoch_time - offset - DateTimeHelper.baseTime
        if rtc > 0xFFFFFFFF:
            rtc = 0xFFFFFFFF
        # print ' ### DateTimeHelper.rtcFromDate rtc:0x{0:x} {0} offset:0x{1:x} {1} epoch_time:0x{2:x} {2}'.format(rtc, offset, epoch_time)
        return rtc

class NumberHelper(object):
    @staticmethod
    def make_32bit_int_from_nbit_signed_int(signed_value, n_bits):
        sign = ((0xFFFFFFFF << n_bits) & 0xFFFFFFFF) * ((signed_value >> n_bits - 1) & 1)
        return (sign | signed_value) & 0xFFFFFFFF

class BinaryDataDecoder(object):
    @staticmethod
    def read_uint64be(bin_data, offset):
        return struct.unpack('>Q', bin_data[offset:offset + 8])[0]

    @staticmethod
    def read_uint32be(bin_data, offset):
        return struct.unpack('>I', bin_data[offset:offset + 4])[0]

    @staticmethod
    def read_uint16be(bin_data, offset):
        return struct.unpack('>H', bin_data[offset:offset + 2])[0]

    @staticmethod
    def read_byte(bin_data, offset):
        return struct.unpack('>B', bin_data[offset:offset + 1])[0]

class Config( object ):
    data = None

    def __init__(self, stick_serial):
        self.conn = sqlite3.connect( 'read_minimed.sqlite3' )
        self.c = self.conn.cursor()
        self.c.execute( '''CREATE TABLE IF NOT EXISTS config ( stick_serial TEXT PRIMARY KEY, hmac TEXT, key TEXT, last_radio_channel INTEGER )''' )
        self.c.execute( "INSERT OR IGNORE INTO config VALUES ( ?, ?, ?, ? )", (stick_serial, '', '', 0x14))
        self.conn.commit()

        self.load_config(stick_serial)

    def load_config(self, stick_serial):
        self.c.execute( 'SELECT * FROM config WHERE stick_serial = ?', (stick_serial,))
        self.data = self.c.fetchone()

    @property
    def stick_serial(self):
        return self.data[0]

    @property
    def last_radio_channel(self):
        return self.data[3]

    @last_radio_channel.setter
    def last_radio_channel( self, value ):
        self.c.execute( "UPDATE config SET last_radio_channel = ? WHERE stick_serial = ?", ( value, self.stick_serial ) )
        self.conn.commit()
        self.load_config( self.stick_serial )

    @property
    def hmac(self):
        return self.data[1]

    @hmac.setter
    def hmac( self, value ):
        self.c.execute( "UPDATE config SET hmac = ? WHERE stick_serial = ?", ( value, self.stick_serial ) )
        self.conn.commit()
        self.load_config( self.stick_serial )

    @property
    def key(self):
        return self.data[2]

    @key.setter
    def key( self, value ):
        self.c.execute( "UPDATE config SET key = ? WHERE stick_serial = ?", ( value, self.stick_serial ) )
        self.conn.commit()
        self.load_config( self.stick_serial )

class MedtronicCnlSession ( object ):
    radio_channel = None
    cnl_sequence_number = 1    # cnlSequenceNumber
    medtronic_sequence_number = 1  # medtronicSequenceNumber
    com_d_sequence_number = 1 # comDSequenceNumber
    config = None
    _stick_serial = None
    _pump_mac = None
    _link_mac = None
    _key = None

    @property
    def hmac(self):
        serial = bytearray( re.sub( r"\d+-", "", self.stick_serial ), 'ascii' )
        padding_key = b"A4BD6CED9A42602564F413123"
        digest = hashlib.sha256(serial + padding_key).hexdigest()
        return "".join(reversed([digest[i:i+2] for i in range(0, len(digest), 2)]))

    @property
    def hex_key(self):
        if self.config.key == "":
            raise Exception( "Key not found in config database. Run get_hmac_and_key.py to get populate hmac and key." )
        return self.config.key

    @property
    def stick_serial(self):
        return self._stick_serial

    @stick_serial.setter
    def stick_serial( self, value ):
        self._stick_serial = value
        self.config = Config( self.stick_serial )
        self.radio_channel = self.config.last_radio_channel

    @property
    def link_mac(self):
        return self._link_mac

    @link_mac.setter
    def link_mac( self, value ):
        self._link_mac = value

    @property
    def pump_mac(self):
        return self._pump_mac

    @pump_mac.setter
    def pump_mac( self, value ):
        self._pump_mac = value

    @property
    def link_serial(self):
        return self.link_mac & 0xffffff

    @property
    def pump_serial(self):
        return self.pump_mac & 0xffffff

    @property
    def key(self):
        return self._key

    @key.setter
    def key( self, value ):
        self._key = value

    @property
    def iv(self):
        tmp = bytearray()
        tmp.append(self.radio_channel)
        tmp += self.key[1:]
        return bytes(tmp)


# TODO FIX ME!!!! (if posible)
class MedtronicMessage( object ):
    ENVELOPE_SIZE = 2

    def __init__(self, command_action=None, session=None, payload=None, message_type = None, offset = None):
        self.message_type = message_type
        self.command_action = command_action
        self.session = session
        self.offset = offset
        self.pump_datetime = None
        # self.segment_size = None
        # self.packet_size = None
        # self.last_packet_size = None
        # self.packets_to_fetch = None
        self.packet_number = None
        # self.segmentParams = None
        self.carb_ratios = None
        self.targets = None
        self.sensitivity = None
        self.ehs_mmode = None
        self.nakcmd = None
        self.nakcode = None


        if payload:
            self.set_payload(payload)

    def set_payload(self, payload):
        self.payload = payload
        self.envelope = struct.pack( '<BB',
                                     self.command_action,
                                     len( self.payload ) + self.ENVELOPE_SIZE)

    @classmethod
    def calculate_ccitt(self, data):
        crc = crc16.crc16xmodem( bytes(data), 0xffff )
        return crc & 0xffff

    def pad( self, x, n = 16 ):
        p = n - ( len( x ) % n )
        return x + bytes(bytearray(p)) #chr(p) * p

    # Encrpytion equivalent to Java's AES/CFB/NoPadding mode
    def encrypt( self, clear ):
        cipher = Crypto.Cipher.AES.new(
            key=self.session.key,
            mode=Crypto.Cipher.AES.MODE_CFB,
            IV=self.session.iv,
            segment_size=128
        )

        encrypted = cipher.encrypt(self.pad(clear))[0:len(clear)]
        return encrypted

    # Decryption equivalent to Java's AES/CFB/NoPadding mode
    def decrypt( self, encrypted ):
        cipher = Crypto.Cipher.AES.new(
            key=self.session.key,
            mode=Crypto.Cipher.AES.MODE_CFB,
            IV=self.session.iv,
            segment_size=128
        )

        decrypted = cipher.decrypt(self.pad(encrypted))[0:len(encrypted)]
        return decrypted

    def encode(self):
        # Increment the Medtronic Sequence Number
        self.session.medtronic_sequence_number += 1
        if (self.session.medtronic_sequence_number & 0x7F) == 0:
            self.session.medtronic_sequence_number = 1

        message = self.envelope + self.payload
        crc = struct.pack( '<H', crc16.crc16xmodem( message, 0xffff ) & 0xffff )
        return message + crc

    @classmethod
    def decode( cls, message, session ):
        response = cls()
        response.session = session
        response.envelope = message[0:2]
        response.payload = message[2:-2]
        response.originalMessage = message

        checksum = struct.unpack( '<H', message[-2:] )[0]
        calc_checksum = MedtronicMessage.calculate_ccitt(response.envelope + response.payload)
        if( checksum != calc_checksum ):
            logger.debug('Expected to get {0}. Got {1}'.format( calc_checksum, checksum ))
            # raise ChecksumException( 'Expected to get {0}. Got {1}'.format( calc_checksum, checksum ) )

        return response

# public class ChannelRequestMessage extends MedtronicRequestMessage<ChannelNegotiateResponseMessage> {
class ChannelNegotiateMessage( MedtronicMessage ):
    def __init__( self, session ):
        MedtronicMessage.__init__( self, CommandAction.JOIN_NETWORK, session )

        # The medtronic_sequence_number is always sent as 1 for this message,
        # even though the sequence should keep incrementing as normal

        # The MedtronicMessage sequence number is always sent as 1 for this message
        # addendum: when network is joined the send sequence number is 1 (first pump request-response)
        # sequence should then be 2 and increment for ongoing messages

        payload = struct.pack( '<BB8s',
                               1, # medtronic_sequence_number
                               session.radio_channel,
                               b'\x00\x00\x00\x07\x07\x00\x00\x02' # unknown bytes
                               )
        payload += struct.pack( '<Q', session.link_mac)
        payload += struct.pack( '<Q', session.pump_mac)

        self.set_payload(payload)

class MedtronicSendMessage( MedtronicMessage ):

    # MedtronicSendMessage:
    # +-----------------+------------------------------+--------------+-------------------+--------------------------------+
    # | LE long pumpMAC | byte medtronicSequenceNumber | byte unknown | byte Payload size | byte[] Encrypted Payload bytes |
    # +-----------------+------------------------------+--------------+-------------------+--------------------------------+
    #
    # MedtronicSendMessage (decrypted payload):
    # +-------------------------+--------------------------+----------------------+--------------------+
    # | byte sendSequenceNumber | BE short messageType     | byte[] Payload bytes | BE short CCITT CRC |
    # +-------------------------+--------------------------+----------------------+--------------------+

    # note: pazaan tidepool docs have encrypted/speed mode flags the other way around but testing indicates that this is the way it should be
    # 0x10 always needed for encryption or else there is a timeout
    # 0x01 optional but using this does increase comms speed without needing to engage EHSM session request
    # 0x01 must be set when EHSM session is operational or risk pump radio channel changing
    # I suspect that BeginEHSM / EndEHSM are only ever needed if bulk data is being sent to pump!
    # The 0x01 flag may only be absolutely required when the pump sends a EHSM request during multi-packet transfers

    def __init__(self, message_type, session, payload=None):
        MedtronicMessage.__init__( self, CommandAction.TRANSMIT_PACKET, session )

        mode_flags = 0x10 # encrypted mode

        if message_type == ComDCommand.HIGH_SPEED_MODE_COMMAND:
            seq_no = 0x80
        else:
            seq_no = self.session.com_d_sequence_number
            self.session.com_d_sequence_number += 1
            if (self.session.com_d_sequence_number & 0x7F) == 0:
                self.session.com_d_sequence_number = 1
            mode_flags = mode_flags | 0x01 # high speed mode

        encrypted_payload = struct.pack( '>BH', seq_no, message_type)
        if payload:
            encrypted_payload += payload
        crc = crc16.crc16xmodem( encrypted_payload, 0xffff )
        encrypted_payload += struct.pack( '>H', crc & 0xffff )

        logger.debug("### PAYLOAD")
        logger.debug(binascii.hexlify( encrypted_payload ))

        mm_payload = struct.pack( '<QBBB',
                                 self.session.pump_mac,
                                 self.session.medtronic_sequence_number,
                                 mode_flags,  # Mode flags
                                 len( encrypted_payload )
                                 )
        mm_payload += self.encrypt( encrypted_payload )

        self.set_payload( mm_payload )

class MedtronicReceiveMessage( MedtronicMessage ):
    def __init__(self, command_action=None, session=None, payload=None, message_type=None):
        super().__init__(command_action, session, payload, message_type)
        self.response_payload = None

    @classmethod
    def decode( cls, message, session ):
        response = MedtronicMessage.decode( message, session )

        response.response_envelope = response.payload[0:22]
        decrypted_response_payload = response.decrypt( bytes(response.payload[22:]) )

        response.response_payload = decrypted_response_payload[0:-2]

        logger.debug("### DECRYPTED PAYLOAD:")
        logger.debug(binascii.hexlify(response.response_payload))

        if len(response.response_payload) > 2:
            checksum = struct.unpack( '>H', decrypted_response_payload[-2:])[0]
            calc_checksum = MedtronicMessage.calculate_ccitt(response.response_payload)
            if( checksum != calc_checksum ):
                raise ChecksumException( 'Expected to get {0}. Got {1}'.format( calc_checksum, checksum ) )

        response.__class__ = MedtronicReceiveMessage

        logger.debug( "#### -> messageType: 0x{0:X}".format(response.message_type))

        if response.message_type == ComDCommand.TIME_RESPONSE:
            response.__class__ = PumpTimeResponseMessage
        elif response.message_type == ComDCommand.READ_HISTORY_INFO_RESPONSE:
            response.__class__ = PumpHistoryInfoResponseMessage
        elif response.message_type == ComDCommand.READ_PUMP_STATUS_RESPONSE:
            response.__class__ = PumpStatusResponseMessage

        elif response.message_type == ComDCommand.READ_BOLUS_WIZARD_CARB_RATIOS_RESPONSE:
            response.__class__ = BolusWizardCarbRatiosResponseMessage
        elif response.message_type == ComDCommand.READ_BOLUS_WIZARD_BG_TARGETS_RESPONSE:
            response.__class__ = BolusWizardTargetsResponseMessage
        elif response.message_type == ComDCommand.READ_BOLUS_WIZARD_SENSITIVITY_FACTORS_RESPONSE:
            response.__class__ = BolusWizardSensitivityResponseMessage

        elif response.message_type == ComDCommand.READ_BASAL_PATTERN_RESPONSE:
            response.__class__ = PumpBasalPatternResponseMessage


        elif response.message_type == ComDCommand.INITIATE_MULTIPACKET_TRANSFER:
            response.__class__ = InitMultiPacketSegment
        elif response.message_type == ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION:
            response.__class__ = MultiPacketSegment
        elif response.message_type == ComDCommand.MULTIPACKET_RESEND_PACKETS:
            response.__class__ = MultiPacketSegment
        elif response.message_type == ComDCommand.END_HISTORY_TRANSMISSION:
            response.__class__ = MultiPacketSegment
        elif response.message_type == ComDCommand.HIGH_SPEED_MODE_COMMAND:
            response.__class__ = StatusEHSMmode
        elif response.message_type == ComDCommand.NAK_COMMAND:
            response.__class__ = NakCommand

        return response

    @property
    def message_type(self):
        return struct.unpack( '>H', self.response_payload[1:3])[0]

class BeginEHSMMessage( MedtronicSendMessage ):
    def __init__( self, session ):
        payload = struct.pack( '>B', 0x00 )
        MedtronicSendMessage.__init__(self, ComDCommand.HIGH_SPEED_MODE_COMMAND, session, payload)

class FinishEHSMMessage( MedtronicSendMessage ):
    def __init__( self, session ):
        # Not sure what the payload byte means, but it's the same every time (0x01)
        payload = struct.pack( '>B', 0x01 )
        MedtronicSendMessage.__init__(self, ComDCommand.HIGH_SPEED_MODE_COMMAND, session, payload)

class PumpTimeRequestMessage( MedtronicSendMessage ):
    def __init__( self, session ):
        MedtronicSendMessage.__init__(self, ComDCommand.TIME_REQUEST, session)

class PumpStatusRequestMessage( MedtronicSendMessage ):
    def __init__( self, session ):
        MedtronicSendMessage.__init__(self, ComDCommand.READ_PUMP_STATUS_REQUEST, session)

class PumpBasalPatternRequestMessage( MedtronicSendMessage ):
    def __init__( self, session , basal_pattern):
        payload = struct.pack('>B', basal_pattern)
        MedtronicSendMessage.__init__(self, ComDCommand.READ_BASAL_PATTERN_REQUEST, session, payload)

class BolusWizardCarbRatiosRequestMessage( MedtronicSendMessage ):
    def __init__( self, session ):
        MedtronicSendMessage.__init__(self, ComDCommand.READ_BOLUS_WIZARD_CARB_RATIOS_REQUEST, session)

class BolusWizardTargetsRequestMessage( MedtronicSendMessage ):
    def __init__( self, session ):
        MedtronicSendMessage.__init__(self, ComDCommand.READ_BOLUS_WIZARD_BG_TARGETS_REQUEST, session)

class BolusWizardSensitivityRequestMessage( MedtronicSendMessage ):
    def __init__( self, session ):
        MedtronicSendMessage.__init__(self, ComDCommand.READ_BOLUS_WIZARD_SENSITIVITY_FACTORS_REQUEST, session)

class PumpHistoryInfoRequestMessage( MedtronicSendMessage ):
    def __init__(self, session, date_start, date_end, date_offset, request_type = HistoryDataType.PUMP_DATA):
        from_rtc = DateTimeHelper.rtc_from_date(date_start, date_offset)
        to_rtc = DateTimeHelper.rtc_from_date(date_end, date_offset)
        payload = struct.pack( '>BBIIH', request_type, HistoryRangeType.PARTIAL_HISTORY, from_rtc, to_rtc, 0x00 )
        MedtronicSendMessage.__init__(self, ComDCommand.READ_HISTORY_INFO_REQUEST, session, payload)

class PumpHistoryRequestMessage( MedtronicSendMessage ):
    def __init__(self, session, date_start, date_end, date_offset, request_type = HistoryDataType.PUMP_DATA):
        from_rtc = DateTimeHelper.rtc_from_date(date_start, date_offset)
        to_rtc = DateTimeHelper.rtc_from_date(date_end, date_offset)
        payload = struct.pack( '>BBIIH', request_type, HistoryRangeType.PARTIAL_HISTORY, from_rtc, to_rtc, 0x00 )
        MedtronicSendMessage.__init__(self, ComDCommand.READ_HISTORY_REQUEST, session, payload)

class AckMultipacketRequestMessage( MedtronicSendMessage ):
    def __init__(self, session, segment_command):
        payload = struct.pack( '>H', segment_command)
        MedtronicSendMessage.__init__(self, ComDCommand.ACK_MULTIPACKET_COMMAND, session, payload)

class MultipacketResendPacketsMessage( MedtronicSendMessage ):
    def __init__(self, session, packet_number, missing):
        payload = struct.pack( '>HH', packet_number, missing)
        MedtronicSendMessage.__init__(self, ComDCommand.MULTIPACKET_RESEND_PACKETS, session, payload)

class MultipacketSession( object ):

    session_size = None
    packet_size = None
    last_packet_size = None
    packets_to_fetch = None
    response = None
    segments = None
    segments_filled = None
    last_packet_number = None

    def __init__(self, settings ):
        MultipacketSession.session_size = settings.segment_size
        MultipacketSession.packet_size = settings.packet_size
        MultipacketSession.last_packet_size = settings.last_packet_size
        MultipacketSession.packets_to_fetch = settings.packets_to_fetch
        MultipacketSession.response = [None] * settings.packets_to_fetch
        # MultipacketSession.response = bytearray(self.session_size + 1)
        # MultipacketSession.response[0] = settings.com_d_sequence_number # comDSequenceNumber
        MultipacketSession.segments = [None] * settings.packets_to_fetch
        MultipacketSession.segments_filled = 0
        MultipacketSession.last_packet_number = MultipacketSession.packets_to_fetch - 1
        logger.debug("### Start MultipacketSession")


    @classmethod
    def payload_complete(self):
        # logger.debug("### -> payload_complete: segments_filled: {0}, packets_to_fetch: {1}".format(MultipacketSession.segments_filled, MultipacketSession.packets_to_fetch))
        if MultipacketSession.segments_filled == MultipacketSession.packets_to_fetch:
            return True
        else:
            return False

    @classmethod
    def add_segment (sefl, data):
        packet_number = data.packet_number
        packet_size = data.packet_size
        payload = data.payload

        # logger.debug("### -> add_segment: packet_number: {0}, packet_size: {1}".format(packet_number, packet_size))

        if MultipacketSession.segments[packet_number]:
            logger.debug("### Got a Repeated Multipacket Segment: {0} of {1}, count: {3} [packetSize={4} {5}/{6}]".format(packet_number+1, MultipacketSession.packets_to_fetch, MultipacketSession.segments_filled, packet_size, MultipacketSession.packet_size, MultipacketSession.last_packet_number, MultipacketSession.last_packet_size))
            return False

        if (packet_number == MultipacketSession.last_packet_number) and (packet_size != MultipacketSession.last_packet_size):
            logger.debug("Multipacket Transfer last packet size mismatch")
            return False
        elif (packet_number != MultipacketSession.last_packet_number) and (packet_size != MultipacketSession.packet_size):
            logger.debug("Multipacket Transfer packet size mismatch")
            return False

        MultipacketSession.segments[packet_number] = True
        MultipacketSession.segments_filled = MultipacketSession.segments_filled + 1

        logger.info("### Got a Multipacket Segment: {0} of {1}, count: {3} [packetSize={4} {5}/{6}]".format(packet_number+1, MultipacketSession.packets_to_fetch, MultipacketSession.segments_filled, packet_size, MultipacketSession.packet_size, MultipacketSession.last_packet_number, MultipacketSession.last_packet_size))

        # buffer1[pos:pos+len(buffer2)] = buffer2
        #MultipacketSession.response[(packet_number * MultipacketSession.packet_size) + 1 : packet_size] = payload
        MultipacketSession.response[packet_number] = payload

        return True

    @classmethod
    def missing_segments(sefl):
        packet_number = 0
        missing = 0
        for segment in MultipacketSession.segments:
            if segment:
                if missing > 0:
                    break
                packet_number = packet_number + 1
            else:
                missing = missing + 1

        logger.debug("### Request Missing Multipacket Segments, position: {0} of {1}, missing: {2}".format(packet_number+1, MultipacketSession.packets_to_fetch, missing))
        return packet_number, missing

# public abstract class ContourNextLinkBinaryRequestMessage<T> extends ContourNextLinkRequestMessage<T> {
class ContourNextLinkBinaryMessage(object):
    def __init__(self, message_type=None, session=None, payload=None):
        self.payload = payload
        self.session = session
        if message_type and self.session:
            self.envelope = struct.pack('<BB6s10sBI5sI',
                                        0x51,
                                        0x03,
                                        b'000000',  # Text of PumpInfo serial, but 000000 for 600 Series pumps
                                        b'\x00' * 10,  # unknown bytes
                                        message_type,  # CommandType
                                        self.session.cnl_sequence_number,
                                        b'\x00' * 5,  # unknown bytes
                                        len(self.payload) if self.payload else 0)

            # Now that we have the payload, calculate the message CRC
            self.envelope += struct.pack('B', self.make_message_crc())

    def make_message_crc(self):
        checksum = 0
        for x in self.envelope[0:32]:
            checksum += ord_hack(x)
        # checksum = sum( bytearray(self.envelope[0:32], 'utf-8') )

        if self.payload:
            checksum += sum(bytearray(self.payload))

        return checksum & 0xff

    def encode(self):
        # Increment the Bayer Sequence Number
        self.session.cnl_sequence_number += 1
        if self.session.cnl_sequence_number & 0xFF  == 0:
            self.session.cnl_sequence_number = 1

        if self.payload:
            return self.envelope + self.payload
        else:
            return self.envelope

    @classmethod
    def decode(cls, message):
        response = cls()
        response.envelope = message[0:33]
        response.payload = message[33:]

        checksum = message[32]
        calc_checksum = response.make_message_crc()
        if (checksum != calc_checksum):
            logger.error('ChecksumException: Expected to get {0}. Got {1}'.format(calc_checksum, checksum))
            raise ChecksumException('Expected to get {0}. Got {1}'.format(calc_checksum, checksum))

        return response

    @property
    def link_device_operation(self):
        return ord_hack(self.envelope[18])

class ReadInfoResponseMessage( object ):
    def __init__(self):
        self.response_payload = None

    @classmethod
    def decode( cls, message ):
        response = cls()
        response.response_payload = message
        return response

    @property
    def link_mac(self):
        return struct.unpack( '>Q', self.response_payload[0:8])[0]

    @property
    def pump_mac(self):
        return struct.unpack( '>Q', self.response_payload[8:16])[0]

class ReadLinkKeyResponseMessage( object ):
    def __init__(self):
        self.response_payload = None

    @classmethod
    def decode( cls, message ):
        response = cls()
        response.response_payload = message
        return response

    @property
    def packed_link_key(self):
        return struct.unpack( '>55s', self.response_payload[0:55])[0]

    def link_key(self, serial_number):
        key = bytearray(b"")
        pos = ord_hack(serial_number[-1:]) & 7

        for it in range(16):
            if (ord_hack(self.packed_link_key[pos + 1]) & 1) == 1:
                key.append(~ord_hack(self.packed_link_key[pos]) & 0xff)
            else:
                key.append(self.packed_link_key[pos])

            if ((ord_hack(self.packed_link_key[pos + 1]) >> 1) & 1) == 0:
                pos += 3
            else:
                pos += 2

        return key

class PumpTimeResponseMessage( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.TIME_RESPONSE:
            raise UnexpectedMessageException( "Expected to get a Time Response message '{0}'. Got {1}.".format(ComDCommand.TIME_RESPONSE, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = PumpTimeResponseMessage
        return response

    @property
    def time_set(self):
        if self.response_payload[3] == 0:
            return False
        else:
            return True

    @property
    def encoded_datetime(self):
        return struct.unpack( '>Q', self.response_payload[4:])[0]

    @property
    def pump_datetime(self):
        date_time_data = self.encoded_datetime
        return DateTimeHelper.decode_date_time(date_time_data)

    @property
    def offset(self):
        date_time_data = self.encoded_datetime
        return DateTimeHelper.decode_date_time_offset(date_time_data)

class PumpStatusResponseMessage( MedtronicReceiveMessage ):
    # mmol = 1
    # mgdl = 2

    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.READ_PUMP_STATUS_RESPONSE:
            raise UnexpectedMessageException( "Expected to get a Status Response message '{0}'. Got {1}.".format(ComDCommand.READ_PUMP_STATUS_RESPONSE, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = PumpStatusResponseMessage
        return response

    # see https://github.com/pazaan/600SeriesAndroidUploader/blob/master/app/src/main/java/info/nightscout/android/medtronic/message/PumpStatusResponseMessage.java

    @property
    def is_pump_status_suspended(self):
        if ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] )  & 0x01 :
            return 1
        else:
            return 0

    @property
    def is_pump_status_bolusing_normal(self):
        if ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] )  & 0x02 :
            return 1
        else:
            return 0

    @property
    def is_pump_status_bolusing_square(self):
        if ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] )  & 0x04 :
            return 1
        else:
            return 0

    @property
    def is_pump_status_bolusing_dual(self):
        if ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] )  & 0x08 :
            return 1
        else:
            return 0

    @property
    def is_pump_status_delivering_insulin(self):
        if ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] )  & 0x10 :
            return 1
        else:
            return 0

    @property
    def is_pump_status_temp_basal_active(self):
        if ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] )  & 0x20 :
            return 1
        else:
            return 0

    @property
    def is_pump_status_cgm_active(self):
        if ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] )  & 0x40 :
            return 1
        else:
            return 0

    @property
    def bolusing_delivered(self):
        return float( struct.unpack( '>I', self.response_payload[0x04:0x08] )[0] ) / 10000

    @property
    def bolusing_minutes_remaining(self):
        return int( struct.unpack( '>H', self.response_payload[0x0c:0x0e] )[0] )

    @property
    def bolusing_reference(self):
        return int( struct.unpack( '>B', self.response_payload[0x0e:0x0f] )[0] )

    @property
    def last_bolus_amount(self):
        return float(struct.unpack('>I', self.response_payload[0x10:0x14])[0]) / 10000

    @property
    def last_bolus_time(self):
        date_time_data = struct.unpack('>L', self.response_payload[0x14:0x18])[0]
        return DateTimeHelper.decode_date_time( date_time_data, 0)

    @property
    def last_bolus_reference(self):
        return int( struct.unpack( '>B', self.response_payload[0x18:0x19] )[0] )

    @property
    def active_basal_pattern(self):
        return int( struct.unpack( '>B', self.response_payload[0x1a:0x1b] )[0] ) & 0x0F

    @property
    def active_temp_basal_pattern(self):
        return int( (struct.unpack( '>B', self.response_payload[0x1a:0x1b] )[0] ) >> 4 ) & 0x0F

    @property
    def current_basal_rate(self):
        return float( struct.unpack( '>I', self.response_payload[0x1b:0x1f] )[0] ) / 10000

    @property
    def temp_basal_rate(self):
        return float( struct.unpack( '>I', self.response_payload[0x1f:0x23] )[0] ) / 10000

    @property
    def temp_basal_percentage(self):
        return int( struct.unpack( '>B', self.response_payload[0x23:0x24] )[0] )

    @property
    def temp_basal_minutes_remaining(self):
        return int( struct.unpack( '>H', self.response_payload[0x24:0x26] )[0] )

    @property
    def basal_units_delivered_today(self):
        return float( struct.unpack( '>I', self.response_payload[0x26:0x2a] )[0] ) / 10000

    @property
    def battery_level_percentage(self):
        return int( struct.unpack( '>B', self.response_payload[0x2a:0x2b] )[0] )

    @property
    def insulin_units_remaining(self):
        return float( struct.unpack( '>I', self.response_payload[0x2b:0x2f] )[0] ) / 10000

    @property
    def minutes_of_insulin_remaining(self):
        hours = int(struct.unpack('>B', self.response_payload[0x2f:0x30])[0])
        minutes = int( struct.unpack( '>B', self.response_payload[0x30:0x31] )[0] )
        return int ((hours * 60) + minutes)

    @property
    def active_insulin(self):
        return float( struct.unpack( '>I', self.response_payload[0x31:0x35] )[0] ) / 10000

    @property
    def sensor_bgl(self):
        # In mg/DL. 0x0000 = no CGM reading, 0x03NN = sensor exception
        return int( struct.unpack( '>H', self.response_payload[0x35:0x37] )[0] )

    @property
    def sensor_bgl_timestamp(self):
        date_time_data = struct.unpack( '>Q', self.response_payload[0x37:0x3f] )[0]
        return DateTimeHelper.decode_date_time( date_time_data )

    @property
    def is_plgm_alert_on_high(self):
        if (struct.unpack('>B', self.response_payload[0x3f:0x40])[0]) & 0x01:
            return 1
        else:
            return 0

    @property
    def is_plgm_alert_on_low(self):
        if (struct.unpack('>B', self.response_payload[0x3f:0x40])[0]) & 0x02:
            return 1
        else:
            return 0

    @property
    def is_plgm_alert_before_high(self):
        if (struct.unpack('>B', self.response_payload[0x3f:0x40])[0]) & 0x04:
            return 1
        else:
            return 0
    @property
    def is_plgm_alert_before_low(self):
        if (struct.unpack('>B', self.response_payload[0x3f:0x40])[0]) & 0x08:
            return 1
        else:
            return 0
    @property
    def is_plgm_alert_suspend(self):
        if (struct.unpack('>B', self.response_payload[0x3f:0x40])[0]) & 0x80:
            return 1
        else:
            return 0
    @property
    def is_plgm_alert_suspend_low(self):
        # needs discovery confirmation!
        if (struct.unpack('>B', self.response_payload[0x3f:0x40])[0]) & 0x10:
            return 1
        else:
            return 0

    @property
    def trend_arrow(self):
        status = int( struct.unpack( '>B', self.response_payload[0x40:0x41] )[0] ) & 0xF0
        if status == 0xc0:
            return 3 #"3 arrows up"
        elif status == 0xa0:
            return 2 #"2 arrows up"
        elif status == 0x80:
            return 1 #"1 arrow up"
        elif status == 0x60:
            return 0 #"No arrows"
        elif status == 0x40:
            return -1 #"1 arrow down"
        elif status == 0x20:
            return -2 #"2 arrows down"
        elif status == 0x00:
            return -3 #"3 arrows down"
        else:
            return None #"Unknown trend"

    @property
    def is_sensor_status_calibrating(self):
        if ( struct.unpack( '>B', self.response_payload[0x41:0x42] )[0] )  & 0x01 :
            return 1
        else:
            return 0

    @property
    def is_sensor_status_calibration_complete(self):
        if ( struct.unpack( '>B', self.response_payload[0x41:0x42] )[0] )  & 0x02 :
            return 1
        else:
            return 0

    @property
    def is_sensor_status_exception(self):
        if ( struct.unpack( '>B', self.response_payload[0x41:0x42] )[0] )  & 0x04 :
            return 1
        else:
            return 0

    @property
    def sensor_cal_minutes_remaining(self):
        return int( struct.unpack( '>H', self.response_payload[0x43:0x45] )[0] )

    @property
    def sensor_battery_level_percentage(self):
        sbatt_raw = int( struct.unpack( '>B', self.response_payload[0x45:0x46] )[0] )
        return int(round(((sbatt_raw & 0x0F) * 100.0) / 15.0))

    @property
    def sensor_rate_of_change(self):
        return float( struct.unpack( '>h', self.response_payload[0x46:0x48] )[0] ) / 100

    @property
    def recent_bolus_wizard(self):
        # Bitfield of the Bolus Wizard status. 0x01 if the Bolus Wizard has been used in the last 15 minutes
        if self.response_payload[0x48] == 0:
            return 0
        else:
            return 1

    @property
    def recent_bgl(self):
        # Blood Glucose Level entered into the Bolus Wizard, in mg/dL
        return struct.unpack( '>H', self.response_payload[0x49:0x4b] )[0]

    #Active alert
    @property
    def alert(self):
        return struct.unpack( '>H', self.response_payload[0x4b:0x4d] )[0]

    @property
    def alert_date(self):
        date_time_data = struct.unpack( '>Q', self.response_payload[0x4d:0x55] )[0]
        return DateTimeHelper.decode_date_time( date_time_data )

    @property
    def is_alert_silence_high(self):
        if (struct.unpack('>B', self.response_payload[0x55:0x56])[0]) & 0x01:
            return 1
        else:
            return 0
    @property

    def is_alert_silence_high_low(self):
        if (struct.unpack('>B', self.response_payload[0x55:0x56])[0]) & 0x02:
            return 1
        else:
            return 0

    @property
    def is_alert_silence_all(self):
        if (struct.unpack('>B', self.response_payload[0x55:0x56])[0]) & 0x04:
            return 1
        else:
            return 0

    @property
    def alert_silence_minutes_remaining(self):
        return struct.unpack( '>H', self.response_payload[0x56:0x58] )[0]

class PumpHistoryInfoResponseMessage( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.READ_HISTORY_INFO_RESPONSE:
            raise UnexpectedMessageException( "Expected to get a Response message '{0}'. Got {1}.".format(ComDCommand.READ_HISTORY_INFO_RESPONSE, response.message_type))
        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = PumpHistoryInfoResponseMessage
        return response

    @property
    def length(self):
        return struct.unpack( '>I', self.response_payload[4:8] )[0]

    @property
    def encoded_datetime_start(self):
        return struct.unpack( '>Q', self.response_payload[8:16] )[0]

    @property
    def encoded_datetime_end(self):
        return struct.unpack( '>Q', self.response_payload[16:24] )[0]

    @property
    def from_date(self):
        date_time_data = self.encoded_datetime_start
        return DateTimeHelper.decode_date_time( date_time_data )

    @property
    def to_date(self):
        date_time_data = self.encoded_datetime_end
        return DateTimeHelper.decode_date_time( date_time_data )

    @property
    def blocks(self):
        return int(self.length / 2048)

class InitMultiPacketSegment ( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.INITIATE_MULTIPACKET_TRANSFER:
            raise UnexpectedMessageException( "Expected to get a Response message '{0}'. Got {1}.".format(ComDCommand.INITIATE_MULTIPACKET_TRANSFER, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = InitMultiPacketSegment
        return response

    @property
    def com_d_sequence_number(self): # comDSequenceNumber
        return struct.unpack( '>B', self.response_payload[0x00:0x01] )[0]

    @property
    def segment_size(self): # sessionSize
        return struct.unpack( '>I', self.response_payload[0x03:0x07] )[0]

    @property
    def packet_size(self): # packetSize
        return struct.unpack( '>H', self.response_payload[0x07:0x09] )[0]

    @property
    def last_packet_size(self): # lastPacketSize
        return struct.unpack( '>H', self.response_payload[0x09:0x0B] )[0]

    @property
    def packets_to_fetch(self): # packetsToFetch
        return struct.unpack( '>H', self.response_payload[0x0B:0x0D] )[0]

class MultiPacketSegment( MedtronicReceiveMessage ):

    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = MultiPacketSegment
        return response

    @property
    def packet_number(self):
        return struct.unpack( '>H', self.response_payload[0x03:0x05] )[0]

    @property
    def packet_size( self ):
        return len(self.response_payload) - 5

    @property
    def payload( self ):
        return self.response_payload[0x05:]

class StatusEHSMmode ( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.HIGH_SPEED_MODE_COMMAND:
            raise UnexpectedMessageException( "Expected to get a Response message '{0}'. Got {1}.".format(ComDCommand.HIGH_SPEED_MODE_COMMAND, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = StatusEHSMmode
        return response

    @property
    def ehs_mmode(self): # EHSMmode
        return ( struct.unpack( '>B', self.response_payload[0x03:0x04] )[0] & 1)

class NakCommand ( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.NAK_COMMAND:
            raise UnexpectedMessageException( "Expected to get a Response message '{0}'. Got {1}.".format(ComDCommand.NAK_COMMAND, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = NakCommand
        return response

    @property
    def nakcmd(self):
        return struct.unpack( '>H', self.response_payload[0x03:0x05] )[0]

    @property
    def nakcode(self):
        return struct.unpack( '>B', self.response_payload[0x05:0x06] )[0]

class BolusWizardCarbRatiosResponseMessage( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.READ_BOLUS_WIZARD_CARB_RATIOS_RESPONSE:
            raise UnexpectedMessageException( "Expected to get a Response message '{0}'. Got {1}.".format(ComDCommand.READ_BOLUS_WIZARD_CARB_RATIOS_RESPONSE, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = BolusWizardCarbRatiosResponseMessage
        return response

    # [8bit] count, { [32bitBE] rate1, [32bitBE] rate2, [8bit] time period (mult 30 min) }
    @property
    def items(self):
        return struct.unpack( '>B', self.response_payload[0x05:0x06])[0]

    @property
    def carb_ratios(self):
        all_carb_ratios = {}
        index = 0x06
        for i in range(self.items):
            rate1 = (struct.unpack('>I', self.response_payload[index:index+0x04])[0]) / 10  # Grams per One Unit Insulin
            rate2 = (struct.unpack('>I', self.response_payload[index+0x04:index+0x08])[0]) / 1000  # Units Insulin per One Exchange
            carb2 = round((15 / rate2), 4)  # One Exchange = 15 Grams Carb
            time = (struct.unpack('>B', self.response_payload[index+0x08:index+0x09])[0]) * 30
            time_str = str(timedelta(minutes=time))
            index += 0x09
            carb = {
                "rate1" : rate1,
                "rate2" : rate2,
                "carb"  : carb2,
                "time_minutes"  : time,
                "time_str"  : time_str
            }
            all_carb_ratios.update({"{0}".format(i+1) : carb })
            logger.debug("TimePeriod: {0}, Rate1: {1}, Rate2: {2}, (as carb = {3}), Time: {4}h {5}m".format((i+1),rate1,rate2,carb2,(time/60),(time%60)))

        return all_carb_ratios

class BolusWizardTargetsResponseMessage( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.READ_BOLUS_WIZARD_BG_TARGETS_RESPONSE:
            raise UnexpectedMessageException( "Expected to get a Response message '{0}'. Got {1}.".format(ComDCommand.READ_BOLUS_WIZARD_BG_TARGETS_RESPONSE, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = BolusWizardTargetsResponseMessage
        return response

    # [8bit] count, { [16bitBE] hi_mgdl, [16bitBE] hi_mmol, [16bitBE] lo_mgdl, [16bitBE] lo_mmol, [8bit] time period (mult 30 min) }
    @property
    def items(self):
        return struct.unpack( '>B', self.response_payload[0x05:0x06])[0]

    @property
    def targets(self):
        all_targets = {}
        index = 0x06
        for i in range(self.items):
            hi_mgdl = (struct.unpack('>H', self.response_payload[index:index+0x02])[0])
            hi_mmol = ((struct.unpack('>H', self.response_payload[index+0x02:index+0x04])[0]) / 10)
            lo_mgdl = (struct.unpack('>H', self.response_payload[index+0x04:index+0x06])[0])
            lo_mmol = ((struct.unpack('>H', self.response_payload[index + 0x06:index + 0x08])[0]) / 10)
            time = (struct.unpack('>B', self.response_payload[index + 0x08:index + 0x09])[0]) * 30
            index += 0x09
            time_str = str(timedelta(minutes=time))

            target = {
                "hi_mgdl" : hi_mgdl,
                "hi_mmol" : hi_mmol,
                "lo_mgdl"  : lo_mgdl,
                "lo_mmol"  : lo_mmol,
                "time_minutes"  : time,
                "time_str"  : time_str
            }
            all_targets.update({"{0}".format(i+1) : target })
            logger.debug("TimePeriod: {0}, hi_mgdl: {1}, hi_mmol: {2}, lo_mgdl: {3}, lo_mmol: {4}, Time: {5}h {6}m".format((i+1),hi_mgdl,hi_mmol,lo_mgdl,lo_mmol,(time/60),(time%60)))

        return all_targets

class BolusWizardSensitivityResponseMessage( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.READ_BOLUS_WIZARD_SENSITIVITY_FACTORS_RESPONSE:
            raise UnexpectedMessageException( "Expected to get a Response message '{0}'. Got {1}.".format(ComDCommand.READ_BOLUS_WIZARD_SENSITIVITY_FACTORS_RESPONSE, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = BolusWizardSensitivityResponseMessage
        return response

    # [8bit] count, { [32bitBE] isf_mgdl, [32bitBE] isf_mmol, [8bit] time period (mult 30 min) }
    @property
    def items(self):
        return struct.unpack( '>B', self.response_payload[0x05:0x06])[0]

    @property
    def sensitivity(self):
        all_sensitivity = {}
        index = 0x06
        for i in range(self.items):
            isf_mgdl = (struct.unpack('>H', self.response_payload[index:index+0x02])[0])
            isf_mmol = ((struct.unpack('>H', self.response_payload[index+0x02:index+0x04])[0]) / 10)
            time = (struct.unpack('>B', self.response_payload[index + 0x04:index + 0x05])[0]) * 30
            index += 0x05
            time_str = str(timedelta(minutes=time))

            target = {
                "isf_mgdl" : isf_mgdl,
                "isf_mmol" : isf_mmol,
                "time_minutes"  : time,
                "time_str"  : time_str,

            }
            all_sensitivity.update({"{0}".format(i+1) : target })
            logger.debug("TimePeriod: {0}, isf_mgdl: {1}, isf_mmol: {2}, Time: {3}h {4}m".format((i+1),isf_mgdl,isf_mmol,(time/60),(time%60)))

        return all_sensitivity

class PumpBasalPatternResponseMessage( MedtronicReceiveMessage ):
    @classmethod
    def decode( cls, message, session ):
        response = MedtronicReceiveMessage.decode( message, session )
        if response.message_type != ComDCommand.READ_BASAL_PATTERN_RESPONSE:
            raise UnexpectedMessageException( "Expected to get a Pump Basal Pattern Response message '{0}'. Got {1}.".format(ComDCommand.READ_BASAL_PATTERN_RESPONSE, response.message_type))

        # Since we only add behaviour, we can cast this class to ourselves
        response.__class__ = PumpBasalPatternResponseMessage
        return response

class Medtronic600SeriesDriver( object ):
    USB_BLOCKSIZE = 64
    USB_VID = 0x1a79
    USB_PID = 0x6210
    MAGIC_HEADER = b'ABC'

    ERROR_CLEAR_TIMEOUT_MS   = 25000
    PRESEND_CLEAR_TIMEOUT_MS = 50
    READ_TIMEOUT_MS          = 25000
    CNL_READ_TIMEOUT_MS      = 2000

    MULTIPACKET_SEGMENT_MS   = 50   # time allowance per segment
    MULTIPACKET_TIMEOUT_MS   = 1500 # minimum timeout
    MULTIPACKET_SEGMENT_RETRY= 10

    CHANNELS = [ 0x14, 0x11, 0x0e, 0x17, 0x1a ] # In the order that the CareLink applet requests them

    session = None
    def __init__(self):
        self.session = MedtronicCnlSession()
        self.device = None
        self.device_info = None

    @property
    def device_serial(self):
        if not self.device_info:
            return None
        else:
            return self.device_info[0][4][3][1]

    @property
    def device_model(self):
        if not self.device_info:
            return None
        else:
            return self.device_info[0][4][0][0]

    @property
    def device_sn(self):
        if not self.device_info:
            return None
        else:
            return self.device_info[0][4][3][3]

    @property
    def pump_time(self):
        if not self.datetime:
            return None
        else:
            return self.datetime

    @property
    def pump_time_drift(self):
        if not self.drift:
            return None
        else:
            return self.drift

    def open_device(self):
        logger.debug("# Opening device")
        for d in hid.enumerate(self.USB_VID, self.USB_PID):
            if d['vendor_id'] == self.USB_VID and d['product_id'] == self.USB_PID:
                self.device = hid.device()
                self.device.open(self.USB_VID, self.USB_PID)

                logger.debug("Manufacturer: %s" % self.device.get_manufacturer_string())
                logger.debug("Product: %s" % self.device.get_product_string())
                logger.debug("Serial No: %s" % self.device.get_serial_number_string())
                return True
        return False

    def close_device(self):
        logger.debug("# Closing device")
        self.device.close()

    # protected byte[] read_message(UsbHidDriver mDevice, int timeout) throws IOException, TimeoutException {
    def read_message( self, timeout_ms=READ_TIMEOUT_MS ):
        payload = bytearray()
        bytes_read = 0
        payload_size = 0
        expected_size = 0
        first = True

        logger.debug('# Read message, timeout: {0}'.format(timeout_ms))

        while first or (bytes_read > 0 and payload_size == self.USB_BLOCKSIZE-4 and len(payload) != expected_size):
            t = timeout_ms if first else 1500
            logger.debug("timeout = {0}".format(t))
            data = self.device.read( self.USB_BLOCKSIZE, timeout_ms = t )
            first = False
            if data:
                bytes_read = len(data)
                payload_size = data[3]
                if bytearray( data[0:3] ) != self.MAGIC_HEADER :
                    logger.error('## Recieved invalid USB packet')
                    break
                    # raise RuntimeError( 'Recieved invalid USB packet')
                payload.extend( data[4:data[3] + 4] )

                # get the expected size for 0x80 or 0x81 messages as they may be on a block boundary
                if expected_size == 0 and data[3] >= 0x21  and ((data[0x12 + 4] & 0xFF == 0x80) or (data[0x12 + 4] & 0xFF == 0x81)):
                    expected_size = 0x21 + ((data[0x1C + 4] & 0x00FF) | (data[0x1D + 4] << 8 & 0xFF00))

                logger.debug('READ: bytesRead={0}, payloadSize={1}, expectedSize={2}'.format(bytes_read, payload_size, expected_size))

            else:
                logger.debug('Timeout waiting for message')
                raise TimeoutException( 'Timeout waiting for message' )

        logger.debug("READ: {0}".format(binascii.hexlify( payload )))
        return payload

    # intercept unexpected messages from the CNL
    # these usually come from pump requests as it can occasionally resend message responses several times (possibly due to a missed CNL ACK during CNL-PUMP comms?)
    # mostly noted on the higher radio channels, channel 26 shows this the most
    # if these messages are not cleared the CNL will likely error needing to be unplugged to reset as it expects them to be read before any further commands are sent

    # testing:
    # post-clear: send request --> read and drop any message that is not the expected 0x81 response
    # this works if only one message needs to be cleared with the next being the expected 0x81
    # if there is more then one message to be cleared then there is no 0x81 response and the CNL will E86 error
    # pre-clear: clear all messages in stream until timeout --> send request
    # consistently stable even with a small timeout, clears multiple messages with very rare miss
    # which will get caught using the post-clear method as fail-safe

    # protected int clear_message(UsbHidDriver mDevice, int timeout) throws IOException {
    def clear_message(self, timeout_ms=ERROR_CLEAR_TIMEOUT_MS):

        logger.debug("## CLEAR: timeout={0}".format(timeout_ms))

        count = 0
        cleared = False

        while not cleared:
            try:
                payload = self.read_message(timeout_ms)
                count += 1

                # the following are always seen as the end of an incoming stream and can be considered as completed clear indicators

                # check for 'no pump response'
                # 55 | 0B | 00 00 | 00 02 00 00 03 00 00
                if len(payload) == 0x2E and payload[0x21] == 0x55 and payload[0x23] == 0x00 and payload[0x24] == 0x00 and payload[0x26] == 0x02 and payload[0x29] == 0x03:
                    logger.warning("## CLEAR: got 'no pump response' message indicating stream cleared")
                    cleared = True

                elif len(payload) == 0x30 and payload[0x21] == 0x55  and payload[0x24] == 0x00 and payload[0x25] == 0x00 and payload[0x26] == 0x02 and payload[0x29] == 0x02 and payload[0x2B] == 0x01:
                    logger.warning("## CLEAR: got message containing '55 0D 00 00 00 02 00 00 02 00 01 XX XX' (lost pump connection)")
                    cleared = True

                # check for 'non-standard network connect'
                # standard 'network connect' 0x80 response
                # 55 | 2C | 00 04 | xx xx xx xx xx | 02 | xx xx xx xx xx xx xx xx | 82 | 00 00 00 00 00 | 07 | 00 | xx | xx xx xx xx xx xx xx xx | 42 | 00 00 00 00 00 00 00 | xx
                # 55 | size | type | pump serial | ... | pump mac | ... | ... | ... | rssi | cnl mac | ... | ... | channel
                # difference to the standard 'network connect' response
                # -- | -- | 00 00 | -- -- -- -- -- | -- | -- -- -- -- -- -- -- -- | 83 | -- -- -- -- -- | -- | xx | -- | -- -- -- -- -- -- -- -- | 43 | -- -- -- -- -- -- -- | --
                elif len(payload) == 0x4F and payload[0x21] == 0x55 and payload[0x23] == 0x00 and payload[0x24] == 0x00 and (payload[0x33] & 0xFF) == 0x83 and payload[0x44] == 0x43:
                    logger.warning("## CLEAR: got 'non-standard network connect' message indicating stream cleared")
                    cleared = True

            except TimeoutException:
                cleared = True

        if count > 0:
           logger.warning("## CLEAR: message stream cleared " + str(count) + " messages.")

        return count

    # protected byte[] readResponse0x80(UsbHidDriver mDevice, int timeout, String tag) throws IOException, TimeoutException, UnexpectedMessageException {
    def read_response0x80(self, timeout_ms=READ_TIMEOUT_MS):

        logger.debug("## readResponse0x80")

        read_message_completed = False
        payload = None
        while read_message_completed != True:
            payload = self.read_message(timeout_ms)
            if len(payload) == 0x2E:
                # seen during multipacket transfers, may indicate a full CNL receive buffer
                if payload[0x24] == 0x06 and (payload[0x25] & 0xFF) == 0x88 and payload[0x26] == 0x00 and payload[0x27] == 0x65:
                    logger.debug("## Full CNL receive buffer, read again")
                else:
                    read_message_completed = True
            else:
                read_message_completed = True

        # minimum 0x80 message size?
        if len(payload) <= 0x21:
            logger.error("readResponse0x80: message size <= 0x21")
            self.clear_message()
            #raise UnexpectedMessageException(("0x80 response message size less then expected")

        # 0x80 message?
        if (payload[0x12] & 0xFF) != 0x80:
            logger.error("readResponse0x80: message not a 0x80")
            self.clear_message()
            raise UnexpectedMessageException("0x80 response message not a 0x80")

        # message and internal payload size correct?
        if len(payload) != (0x21 + payload[0x1C] & 0x00FF | payload[0x1D] << 8 & 0xFF00):
            logger.error("readResponse0x80: message size mismatch")
            self.clear_message()
            raise UnexpectedMessageException("0x80 response message size mismatch")

        # 1 byte response? (generally seen as a 0x00 or 0xFF, unknown meaning and high risk of CNL E86 follows)
        if len(payload) == 0x22:
            logger.error("readResponse0x80: message with 1 byte internal payload")
            # do not retry, end the session
            raise UnexpectedMessageException("0x80 response message internal payload is 0x..., connection lost")

        # internal 0x55 payload?
        elif payload[0x21] != 0x55:
            logger.error("readResponse0x80: message no internal 0x55")
            self.clear_message()
            # do not retry, end the session
            raise UnexpectedMessageException("0x80 response message internal payload not a 0x55, connection lost")

        if len(payload) == 0x2E:
            # no pump response?
            if payload[0x24] == 0x00 and payload[0x25] == 0x00 and payload[0x26] == 0x02 and payload[0x27] == 0x00:
                logger.warning("## readResponse0x80: message containing '55 0B 00 00 00 02 00 00 03 00 00' (no pump response)")
                # stream is always clear after this message
                raise UnexpectedMessageException("no response from pump")

            # no connect response?
            elif payload[0x24] == 0x00 and payload[0x25] == 0x20 and payload[0x26] == 0x00 and payload[0x27] == 0x00:
                logger.debug("## readResponse0x80: message containing '55 0B 00 00 20 00 00 00 03 00 00' (no connect)")

            # bad response?
            # seen during multipacket transfers, may indicate a full CNL receive buffer
            elif payload[0x24] == 0x06 and (payload[0x25] & 0xFF) == 0x88 and payload[0x26] == 0x00 and payload[0x27] == 0x65:
                logger.warning("## readResponse0x80: message containing '55 0B 00 06 88 00 65 XX 03 00 00' (bad response)")

        # lost pump connection?
        elif len(payload) == 0x30 and payload[0x24] == 0x00 and payload[0x25] == 0x00 and payload[0x26] == 0x02 and payload[0x29] == 0x02 and payload[0x2B] == 0x01:
            logger.error("readResponse0x80: message containing '55 0D 00 00 00 02 00 00 02 00 01 XX XX' (lost pump connection)")
            self.clear_message()
            # do not retry, end the session
            raise UnexpectedMessageException("connection lost")

        # connection
        elif len(payload) == 0x4F:
            # network connect
            # 55 | 2C | 00 04 | xx xx xx xx xx | 02 | xx xx xx xx xx xx xx xx | 82 | 00 00 00 00 00 | 07 | 00 | xx | xx xx xx xx xx xx xx xx | 42 | 00 00 00 00 00 00 00 | xx
            # 55 | size | type | pump serial | ... | pump mac | ... | ... | ... | rssi | cnl mac | ... | ... | channel
            if payload[0x24] == 0x04 and (payload[0x33] & 0xFF) == 0x82 and payload[0x44] == 0x42:
                logger.debug("## readResponse0x80: message containing network connect (pump connected)")

            # non-standard network connect
            # -- | -- | 00 00 | -- -- -- -- -- | -- | -- -- -- -- -- -- -- -- | 83 | -- -- -- -- -- | -- | xx | -- | -- -- -- -- -- -- -- -- | 43 | -- -- -- -- -- -- -- | --
            elif payload[0x24] == 0x00 and (payload[0x33] & 0xFF) == 0x83 and payload[0x44] == 0x43:
                logger.error("readResponse0x80: message containing non-standard network connect (lost pump connection)")
                # stream is always clear after this message
                # do not retry, end the session
                raise UnexpectedMessageException("connection lost")

        return ContourNextLinkBinaryMessage.decode(payload)

    def read_response0x81(self, timeout_ms=READ_TIMEOUT_MS):

        logger.debug("## readResponse0x81")

        try:
            # an 0x81 response is always expected after sending a request
            # keep reading until we get it or timeout
            while True:
                #message = BayerBinaryMessage.decode(self.read_message())
                payload = self.read_message(timeout_ms) # Read USB packet payload
                if len(payload) < 0x21:                 # Check for min length
                    logger.warning("## readResponse0x81: message size less then expected, length = {0}".format(len(payload)))
                elif (payload[0x12] & 0xFF) != 0x81:   # Check operation byte (expect 0x81 SEND_MESSAGE_RESPONSE)
                    logger.warning("## readResponse0x81: message not a 0x81, got a 0x{0:x}".format(payload[0x12]))
                else:
                    break

        except TimeoutException:                       # Timeout in read_message()
            # ugh... there should always be a CNL 0x81 response and if we don't get one
            # it usually ends with a E86 / E81 error on the CNL needing a unplug/plug cycle
            logger.error("readResponse0x81: timeout waiting for 0x81 response")
            raise TimeoutException("Timeout waiting for 0x81 response")

        # Perform more checks

        # empty response?
        if len(payload) <= 0x21:
            logger.error("readResponse0x81: message size <= 0x21")
            self.clear_message()
            # do not retry, end the session
            raise UnexpectedMessageException("0x81 response was empty, connection lost")

        # message and internal payload size correct?
        elif len(payload) != (0x21 + payload[0x1C] & 0x00FF | payload[0x1D] << 8 & 0xFF00):
            logger.error("readResponse0x81: message size mismatch")
            self.clear_message()
            raise UnexpectedMessageException("0x81 response message size mismatch")

        # internal 0x55 payload?
        elif payload[0x21] != 0x55:
            logger.error("readResponse0x81: message no internal 0x55")
            self.clear_message()
            raise UnexpectedMessageException("0x81 response was not a 0x55 message")

        # state flag?
        # standard response:
        # 55 | 0D   | 00 04 | 00 00 00 00 03 00 01 | xx | xx
        # 55 | size | type  | ... | seq | state
        if len(payload) == 0x30:
            if payload[0x2D] == 0x04:
                logger.warning("## readResponse0x81: message [0x2D]==0x04 (noisy/busy)")

            elif payload[0x2D] != 0x02:
                logger.error("readResponse0x81: message [0x2D]!=0x02 (unknown state)")
                self.clear_message()
                raise UnexpectedMessageException("0x81 unknown state flag")

        # connection
        elif len(payload) == 0x27 and payload[0x23] == 0x00 and payload[0x24] == 0x00:
            logger.warning("## network not connected")
        else:
            logger.warning("## readResponse0x81: unknown 0x55 message type")

        return payload

    # protected void sendMessage(UsbHidDriver mDevice) throws IOException {
    def send_message( self, payload ):

        # Clear any message in the receive buffer
        self.clear_message(timeout_ms=self.PRESEND_CLEAR_TIMEOUT_MS)

        # Split the message into 60 byte chunks
        for packet in [ payload[ i: i+60 ] for i in range( 0, len( payload ), 60 ) ]:
            message = struct.pack( '>3sB', self.MAGIC_HEADER, len( packet ) ) + packet
            self.device.write( bytearray( message ) )
            # Debugging
            logger.debug("SEND: %s", binascii.hexlify( message ))

    # public DeviceInfoResponseCommandMessage send(UsbHidDriver mDevice, int millis) throws IOException, TimeoutException, EncryptionException, ChecksumException, UnexpectedMessageException {
    def request_device_info(self):
        logger.debug("# Read Device Info")
        self.send_message( struct.pack( '>B', 0x58 ) )

        while True:
            try:
                logger.debug(' ## Read first message')
                msg1 = self.read_message()

                logger.debug(' ## Read second message')
                msg2 = self.read_message()

                if astm.codec.is_chunked_message( msg1 ):
                    logger.debug(' ## First message is ASTM message')
                    astm_msg = msg1
                    ctrl_msg = msg2
                elif astm.codec.is_chunked_message( msg2 ):
                    logger.debug(' ## Second message is ASTM message')
                    astm_msg = msg2
                    ctrl_msg = msg1
                else:
                    logger.error('readDeviceInfo: Expected to get an ASTM message, but got {0} instead'.format( binascii.hexlify( msg1 ) ))
                    raise RuntimeError( 'Expected to get an ASTM message, but got {0} instead'.format( binascii.hexlify( msg1 ) ) )

                control_char = asciiKey['ENQ']
                if len( ctrl_msg ) > 0 and ctrl_msg[0] != control_char:
                    logger.error(' ### getDeviceInfo: Expected to get an 0x{0:x} control character, got message with length {1} and control char 0x{1:x}'.format( control_char, len( ctrl_msg ), ctrl_msg[0] ))
                    raise RuntimeError( 'Expected to get an 0x{0:x} control character, got message with length {1} and control char 0x{1:x}'.format( control_char, len( ctrl_msg ), ctrl_msg[0] ) )

                self.device_info = astm.codec.decode( bytes( astm_msg ) )
                self.session.stick_serial = self.device_serial

                break

            except TimeoutException:
                self.send_message(struct.pack( '>B', asciiKey['EOT']))

    def check_control_message(self, control_char):
        msg = self.read_message()
        if len( msg ) > 0 and msg[0] != control_char:
            logger.error(' ### checkControlMessage: Expected to get an 0x{0:x} control character, got message with length {1} and control char 0x{1:x}'.format(control_char, len(msg), msg[0]))
            raise RuntimeError( 'Expected to get an 0x{0:x} control character, got message with length {1} and control char 0x{1:x}'.format(control_char, len(msg), msg[0]))

    def enter_control_mode(self):
        logger.debug("# enterControlMode")
        self.send_message(struct.pack( '>B', asciiKey['NAK']))
        self.check_control_message(asciiKey['EOT'])
        self.send_message(struct.pack( '>B', asciiKey['ENQ']))
        self.check_control_message(asciiKey['ACK'])

    def exit_control_mode(self):
        logger.debug("# exitControlMode")
        try:
            self.send_message(struct.pack( '>B', asciiKey['EOT']))
            self.check_control_message(asciiKey['ENQ'])
        except Exception:
            logger.warning("Unexpected error by exitControlMode, ignoring", exc_info = True)

    def enter_passthrough_mode(self):
        logger.debug("# enterPassthroughMode")
        self.send_message( struct.pack( '>2s', b'W|' ) )
        self.check_control_message(asciiKey['ACK'])
        self.send_message( struct.pack( '>2s', b'Q|' ) )
        self.check_control_message(asciiKey['ACK'])
        self.send_message( struct.pack( '>2s', b'1|' ) )
        self.check_control_message(asciiKey['ACK'])

    def exit_passthrough_mode(self):
        logger.debug("# exitPassthroughMode")
        try:
            self.send_message( struct.pack( '>2s', b'W|' ) )
            self.check_control_message(asciiKey['ACK'])
            self.send_message( struct.pack( '>2s', b'Q|' ) )
            self.check_control_message(asciiKey['ACK'])
            self.send_message( struct.pack( '>2s', b'0|' ) )
            self.check_control_message(asciiKey['ACK'])
        except Exception:
            logger.warning("Unexpected error by exitPassthroughMode, ignoring", exc_info = True)

    def open_connection(self):
        logger.debug("# Request Open Connection")

        mt_message = binascii.unhexlify( self.session.hmac )
        bayer_message = ContourNextLinkBinaryMessage( CommandType.OPEN_CONNECTION, self.session, mt_message )
        self.send_message( bayer_message.encode() )
        self.read_message()

    def close_connection(self):
        logger.debug("# Request Close Connection")
        try:
            mt_message = binascii.unhexlify( self.session.hmac )
            bayer_message = ContourNextLinkBinaryMessage( CommandType.CLOSE_CONNECTION, self.session, mt_message )
            self.send_message( bayer_message.encode() )
            self.read_message()
        except Exception:
            logger.warning("Unexpected error by requestCloseConnection, ignoring", exc_info = True)

    def request_read_info(self):
        logger.debug("# Request Read Info")
        bayer_message = ContourNextLinkBinaryMessage( CommandType.READ_INFO, self.session )
        self.send_message( bayer_message.encode() )
        response = ContourNextLinkBinaryMessage.decode( self.read_message() ) # The response is a 0x14 as well
        info = ReadInfoResponseMessage.decode( response.payload )
        self.session.link_mac = info.link_mac
        self.session.pump_mac = info.pump_mac

    def read_link_key(self):
        logger.debug("# Request Read Link Key")
        bayer_message = ContourNextLinkBinaryMessage( CommandType.REQUEST_LINK_KEY, self.session )
        self.send_message( bayer_message.encode() )
        response = ContourNextLinkBinaryMessage.decode( self.read_message() )
        key_request = ReadLinkKeyResponseMessage.decode( response.payload )
        self.session.key = bytes(key_request.link_key(self.session.stick_serial))
        logger.debug("LINK KEY: {0}".format(binascii.hexlify(self.session.key)))

    def negotiate_channel(self):
        logger.debug("# Negotiate pump comms channel")

        # Scan the last successfully connected channel first, since this could save us negotiating time
        for self.session.radio_channel in [self.session.config.last_radio_channel] + self.CHANNELS:
            logger.debug("Negotiating on channel 0x{0:X}".format(self.session.radio_channel))

            mt_message = ChannelNegotiateMessage( self.session )

            bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
            self.send_message( bayer_message.encode() )
            self.read_response0x81()
            response = self.read_response0x80()
            if len( response.payload ) > 0x0D:
                # Check that the channel ID matches
                response_channel = response.payload[0x2B]
                if self.session.radio_channel == response_channel:
                    self.session.radio_rssi_percent = int(((response.payload[0x1A] & 0x00FF) * 100) / 0xA8)
                    break
                else:
                    raise UnexpectedMessageException( "Expected to get a message for channel {0}. Got {1}".format(self.session.radio_channel, response_channel))
            else:
                self.session.radio_channel = None

        if not self.session.radio_channel:
            # Could not negotiate a comms channel with the pump. Are you near to the pump?
            return False
            # raise NegotiationException('Could not negotiate a comms channel with the pump. Are you near to the pump?')
        else:
            self.session.config.last_radio_channel = self.session.radio_channel
        return True

    def begin_ehsm(self):
        logger.debug("# Begin Extended High Speed Mode Session")
        mt_message = BeginEHSMMessage( self.session )

        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81() # The Begin EHSM only has an 0x81 response

    def finish_ehsm(self):
        logger.debug("# Finish Extended High Speed Mode Session")
        mt_message = FinishEHSMMessage( self.session )

        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81() # The Finish EHSM only has an 0x81 response

    def get_medtronic_message(self, expected_message_types, timeout_ms=READ_TIMEOUT_MS):
        message_received = False
        med_message = None
        while message_received == False:
            message = self.read_response0x80(timeout_ms)
            med_message = MedtronicReceiveMessage.decode(message.payload, self.session)
            if med_message.message_type in expected_message_types:
                message_received = True
            else:
                logger.warning("## getMedtronicMessage: waiting for message of [0x{0}], got 0x{1:X}".format(''.join('%04x' % i for i in expected_message_types), med_message.message_type))
        return med_message

    def get_pump_time(self):
        logger.debug("# Get Pump Time")
        mt_message = PumpTimeRequestMessage( self.session )

        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81()
        result = self.get_medtronic_message([ComDCommand.TIME_RESPONSE])
        self.datetime = result.pump_datetime
        self.offset = result.offset
        self.drift = datetime.datetime.now(result.pump_datetime.tzinfo) - self.datetime
        return result

    def get_pump_status(self):
        logger.debug("# Get Pump Status")
        mt_message = PumpStatusRequestMessage( self.session )

        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81()
        response = self.get_medtronic_message([ComDCommand.READ_PUMP_STATUS_RESPONSE])
        return response


    # public byte[] getBolusWizardCarbRatios() throws EncryptionException, IOException, ChecksumException, TimeoutException, UnexpectedMessageException {
    def get_bolus_wizard_carb_ratios(self):
        logger.debug("# Get Bolus Wizard Carb Ratios")
        mt_message = BolusWizardCarbRatiosRequestMessage( self.session)
        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81()
        result = self.get_medtronic_message([ComDCommand.READ_BOLUS_WIZARD_CARB_RATIOS_RESPONSE])
        return result.carb_ratios

    # public byte[] getBolusWizardTargets() throws EncryptionException, IOException, ChecksumException, TimeoutException, UnexpectedMessageException {
    def get_bolus_wizard_targets(self):
        logger.debug("# Get Bolus Wizard Targets")
        mt_message = BolusWizardTargetsRequestMessage( self.session)
        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81()
        result = self.get_medtronic_message([ComDCommand.READ_BOLUS_WIZARD_BG_TARGETS_RESPONSE])
        return result.targets

    # public byte[] getBolusWizardSensitivity() throws EncryptionException, IOException, ChecksumException, TimeoutException, UnexpectedMessageException {
    def get_bolus_wizard_sensitivity(self):
        logger.debug("# Get Bolus Wizard Sensitivity")
        mt_message = BolusWizardSensitivityRequestMessage( self.session)
        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81()
        result = self.get_medtronic_message([ComDCommand.READ_BOLUS_WIZARD_SENSITIVITY_FACTORS_RESPONSE])
        return result.sensitivity

    def get_pump_history_info(self, date_start, date_end, request_type = HistoryDataType.PUMP_DATA):
        logger.debug("# Get Pump History Info")
        mt_message = PumpHistoryInfoRequestMessage(self.session, date_start, date_end, self.offset, request_type)
        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81()
        response = self.get_medtronic_message([ComDCommand.READ_HISTORY_INFO_RESPONSE])
        return response

    def get_pump_history(self, date_start, date_end, request_type = HistoryDataType.PUMP_DATA):
        logger.debug("# Get Pump History")
        expected_segments = 0
        retry = 0
        all_segments = []
        segment = []
        multi_packet_session = None
        decrypted = None

        mt_message = PumpHistoryRequestMessage(self.session, date_start, date_end, self.offset, request_type)

        bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
        self.send_message( bayer_message.encode() )
        self.read_response0x81()

        transmission_completed = False
        while transmission_completed != True:

            if multi_packet_session != None and multi_packet_session.payload_complete() == False:
                while True:
                    if expected_segments < 1:
                        packet_number, missing = multi_packet_session.missing_segments()
                        logger.debug("Sending MultipacketResendPacketsMessage")
                        ack_message = MultipacketResendPacketsMessage(self.session, packet_number, missing)
                        bayer_ack_message = ContourNextLinkBinaryMessage(CommandType.SEND_MESSAGE, self.session,ack_message.encode())
                        self.send_message(bayer_ack_message.encode())
                        self.read_response0x81()

                        expected_segments = missing

                    try:
                        # timeout adjusted for efficiency and to allow for large gaps of missing segments as the pump will keep sending until done
                        if multi_packet_session.segments_filled == 0:
                            # pump may have missed the initial ack, we need to wait the max timeout period
                            timeout = Medtronic600SeriesDriver.READ_TIMEOUT_MS
                        else:
                            timeout = Medtronic600SeriesDriver.MULTIPACKET_SEGMENT_MS * expected_segments
                            if timeout < Medtronic600SeriesDriver.MULTIPACKET_TIMEOUT_MS:
                                timeout = Medtronic600SeriesDriver.MULTIPACKET_TIMEOUT_MS

                        decrypted = self.get_medtronic_message([ComDCommand.INITIATE_MULTIPACKET_TRANSFER,
                                                                ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION,
                                                                ComDCommand.MULTIPACKET_RESEND_PACKETS,
                                                                ComDCommand.END_HISTORY_TRANSMISSION,
                                                                ComDCommand.HIGH_SPEED_MODE_COMMAND,
                                                                ComDCommand.NAK_COMMAND], timeout)
                        retry = 0
                        break
                    except:
                        retry = retry + 1
                        if multi_packet_session.segments_filled == 0:
                            self.clear_message()
                            logger.error("Multisession timeout: failed no segments filled")
                        elif (multi_packet_session.segments_filled * 100) / multi_packet_session.packets_to_fetch < 20:
                            self.clear_message()
                            logger.error("Multisession timeout: failed, missed packets > 80%")
                        elif retry >= Medtronic600SeriesDriver.MULTIPACKET_SEGMENT_RETRY:
                            self.clear_message()
                            logger.error("Multisession timeout: retry failed")

                        logger.error("Multisession timeout: count: {0}/{1} expecting: {2} retry: {3}".format(multi_packet_session.segments_filled, multi_packet_session.packets_to_fetch, expected_segments, retry))
                        expected_segments = 0

                    if retry > 0:
                        break

            else:
                decrypted = self.get_medtronic_message([ComDCommand.INITIATE_MULTIPACKET_TRANSFER,
                                                               ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION,
                                                               ComDCommand.MULTIPACKET_RESEND_PACKETS,
                                                               ComDCommand.END_HISTORY_TRANSMISSION,
                                                               ComDCommand.HIGH_SPEED_MODE_COMMAND,
                                                               ComDCommand.NAK_COMMAND])


            if decrypted.message_type == ComDCommand.NAK_COMMAND:
                self.clear_message()
                # TODO Add decode NAK command
                logger.info("## Pump sent a NAK 0x{0:X}:0x{1:X}".format(decrypted.nakcmd, decrypted.nakcode))


            if decrypted.message_type == ComDCommand.HIGH_SPEED_MODE_COMMAND:
                logger.debug("## getPumpHistory consumed HIGH_SPEED_MODE_COMMAND={0}".format(decrypted.ehs_mmode))
                pass
            elif decrypted.message_type == ComDCommand.INITIATE_MULTIPACKET_TRANSFER:
                logger.info("### getPumpHistory got INITIATE_MULTIPACKET_TRANSFER")

                multi_packet_session = MultipacketSession(decrypted)

                logger.info("### session_size: {0}".format(multi_packet_session.session_size))
                logger.info("### packet_size: {0}".format(multi_packet_session.packet_size))
                logger.info("### last_packet_size: {0}".format(multi_packet_session.last_packet_size))
                logger.info("### packets_to_fetch: {0}".format(multi_packet_session.packets_to_fetch))
                logger.info("### last_packet_number: {0}".format(multi_packet_session.last_packet_number))
                logger.info("### segments_filled: {0}".format(multi_packet_session.segments_filled))


                ack_message = AckMultipacketRequestMessage(self.session, ComDCommand.INITIATE_MULTIPACKET_TRANSFER)
                bayer_ack_message = ContourNextLinkBinaryMessage(CommandType.SEND_MESSAGE, self.session, ack_message.encode())
                self.send_message( bayer_ack_message.encode() )
                self.read_response0x81()

                expected_segments = multi_packet_session.packets_to_fetch

                logger.debug("Start multipacket session")

            elif decrypted.message_type == ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION:
                logger.debug("## getPumpHistory got MULTIPACKET_SEGMENT_TRANSMISSION")

                if multi_packet_session == None:
                    logger.debug("multipacketSession not initiated before segment received")
                if multi_packet_session.payload_complete():
                    logger.debug("Multisession Complete - packet not needed")
                else:
                    if multi_packet_session.add_segment(decrypted):
                        expected_segments = expected_segments - 1

                    if multi_packet_session.payload_complete():
                        logger.debug("Multisession Complete")
                        ack_message = AckMultipacketRequestMessage(self.session, ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION)
                        bayer_ack_message = ContourNextLinkBinaryMessage(CommandType.SEND_MESSAGE, self.session, ack_message.encode())
                        self.send_message( bayer_ack_message.encode() )
                        self.read_response0x81()

                        # Save current segment
                        for x in range(len(multi_packet_session.response)):
                            segment.extend(multi_packet_session.response[x])

                        all_segments.append(bytes(segment))
                        segment = []

            elif decrypted.message_type == ComDCommand.END_HISTORY_TRANSMISSION:
                logger.debug("## getPumpHistory got END_HISTORY_TRANSMISSION")
                transmission_completed = True
            else:
                logger.warning("## getPumpHistory !!! UNKNOWN MESSAGE !!!")
                logger.warning("## getPumpHistory response.messageType: {0:x}".format(decrypted.message_type))

        if transmission_completed:
            return all_segments

        else:
            logger.error("Transmission finished, but END_HISTORY_TRANSMISSION did not arrive")

    def decode_pump_segment(self, encoded_fragmented_segment, history_type=HistoryDataType.PUMP_DATA):
        decoded_blocks = []
        segment_payload = bytes(encoded_fragmented_segment)

        # Decompress the message
        if struct.unpack('>H', segment_payload[0:2])[0] == ComDCommand.UNMERGED_HISTORY_RESPONSE:
            header_size_const = 0x000C # 12
            block_size_const =  0x0800 # 2048

            # It's an UnmergedHistoryUpdateCompressed response. We need to decompress it
            data_type = struct.unpack('>B', segment_payload[2:3])[0]  # Returns a HISTORY_DATA_TYPE
            history_size_compressed = struct.unpack('>I', segment_payload[3:7])[0]  # segmentPayload.readUInt32BE(0x03)
            logger.debug("Compressed: {0}".format(history_size_compressed))
            history_size_uncompressed = struct.unpack('>I', segment_payload[7:11])[0]  # segmentPayload.readUInt32BE(0x07)
            logger.debug("Uncompressed: {0}".format(history_size_uncompressed))
            history_compressed = struct.unpack('>B', segment_payload[11:12])[0]
            logger.debug("IsCompressed: {0}".format(history_compressed))

            if data_type != history_type:  # Check HISTORY_DATA_TYPE (PUMP_DATA: 2, SENSOR_DATA: 3)
                logger.error('History type in response: {0} {1}'.format(type(data_type), data_type))
                logger.error('Unexpected history type in response')
                # TODO Fixme (add exception)

            # Check that we have the correct number of bytes in this message
            if len(segment_payload) - header_size_const != history_size_compressed:
                logger.error('Unexpected message size')
                raise InvalidMessageError('Unexpected message size')

            if history_compressed > 0:
                block_payload = lzo.decompress(segment_payload[header_size_const:], False, history_size_uncompressed)
            else:
                block_payload = segment_payload[header_size_const:]

            if len(block_payload) % block_size_const != 0:
                logger.error('Block payload size is not a multiple of 2048')
                raise InvalidMessageError('Block payload size is not a multiple of 2048')

            for i in range(0, len(block_payload) // block_size_const):
                block_size = struct.unpack('>H', block_payload[(i + 1) * block_size_const - 4: (i + 1) * block_size_const - 2])[0]  # blockPayload.readUInt16BE(((i + 1) * ReadHistoryCommand.BLOCK_SIZE) - 4)
                block_checksum = struct.unpack('>H', block_payload[(i + 1) * block_size_const - 2: (i + 1) * block_size_const])[0]  # blockPayload.readUInt16BE(((i + 1) * ReadHistoryCommand.BLOCK_SIZE) - 2)

                block_start = i * block_size_const
                block_data = block_payload[block_start: block_start + block_size]
                calculated_checksum = MedtronicMessage.calculate_ccitt(block_data)
                if block_checksum != calculated_checksum:
                    logger.error('Unexpected checksum in block')
                    raise InvalidMessageError('Unexpected checksum in block')
                else:
                    decoded_blocks.append(block_data)
        else:
            logger.error('Unknown history response message type')
            raise InvalidMessageError('Unknown history response message type')

        return decoded_blocks

    def decode_events(self, decoded_blocks):
        event_list = []
        for page in decoded_blocks:
            pos = 0

            while pos < len(page):
                event_size = struct.unpack('>B', page[pos + 2: pos + 3])[0]  # page[pos + 2]
                event_data = page[pos: pos + event_size]  # page.slice(pos, pos + eventSize)
                pos += event_size
                event_list.extend(NGPHistoryEvent(event_data).event_instance().all_nested_events())
        return event_list

    def process_pump_history(self, history_segments, history_type=HistoryDataType.PUMP_DATA):
        history_events = []
        for segment in history_segments:
            decoded_blocks = self.decode_pump_segment(segment, history_type)
            history_events += self.decode_events(decoded_blocks)
        for event in history_events:
            event.post_process(history_events)
        return history_events

    def get_pump_basal_pattern_current_number(self):
        expected_segments = 0
        retry = 0
        all_segments = []
        segment = []
        multi_packet_session = None
        decrypted = None

        transmission_completed = False
        while transmission_completed != True:

            if multi_packet_session != None and multi_packet_session.payload_complete() == False:
                while True:
                    if expected_segments < 1:
                        packet_number, missing = multi_packet_session.missing_segments()
                        logger.debug("Sending MultipacketResendPacketsMessage")
                        ack_message = MultipacketResendPacketsMessage(self.session, packet_number, missing)
                        bayer_ack_message = ContourNextLinkBinaryMessage(CommandType.SEND_MESSAGE, self.session,ack_message.encode())
                        self.send_message(bayer_ack_message.encode())
                        self.read_response0x81()

                        expected_segments = missing

                    try:
                        # timeout adjusted for efficiency and to allow for large gaps of missing segments as the pump will keep sending until done
                        if multi_packet_session.segments_filled == 0:
                            # pump may have missed the initial ack, we need to wait the max timeout period
                            timeout = Medtronic600SeriesDriver.READ_TIMEOUT_MS
                        else:
                            timeout = Medtronic600SeriesDriver.MULTIPACKET_SEGMENT_MS * expected_segments
                            if timeout < Medtronic600SeriesDriver.MULTIPACKET_TIMEOUT_MS:
                                timeout = Medtronic600SeriesDriver.MULTIPACKET_TIMEOUT_MS

                        decrypted = self.get_medtronic_message([ComDCommand.INITIATE_MULTIPACKET_TRANSFER,
                                                                ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION,
                                                                ComDCommand.MULTIPACKET_RESEND_PACKETS,
                                                                ComDCommand.END_HISTORY_TRANSMISSION,
                                                                ComDCommand.READ_BASAL_PATTERN_RESPONSE,
                                                                ComDCommand.HIGH_SPEED_MODE_COMMAND,
                                                                ComDCommand.NAK_COMMAND], timeout)
                        retry = 0
                        break
                    except:
                        retry = retry + 1
                        if multi_packet_session.segments_filled == 0:
                            self.clear_message()
                            logger.error("Multisession timeout: failed no segments filled")
                        elif (multi_packet_session.segments_filled * 100) / multi_packet_session.packets_to_fetch < 20:
                            self.clear_message()
                            logger.error("Multisession timeout: failed, missed packets > 80%")
                        elif retry >= Medtronic600SeriesDriver.MULTIPACKET_SEGMENT_RETRY:
                            self.clear_message()
                            logger.error("Multisession timeout: retry failed")

                        logger.error("Multisession timeout: count: {0}/{1} expecting: {2} retry: {3}".format(multi_packet_session.segments_filled, multi_packet_session.packets_to_fetch, expected_segments, retry))
                        expected_segments = 0

                    if retry > 0:
                        break

            else:
                decrypted = self.get_medtronic_message([ComDCommand.INITIATE_MULTIPACKET_TRANSFER,
                                                               ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION,
                                                               ComDCommand.MULTIPACKET_RESEND_PACKETS,
                                                               ComDCommand.END_HISTORY_TRANSMISSION,
                                                               ComDCommand.READ_BASAL_PATTERN_RESPONSE,
                                                               ComDCommand.HIGH_SPEED_MODE_COMMAND,
                                                               ComDCommand.NAK_COMMAND])


            if decrypted.message_type == ComDCommand.NAK_COMMAND:
                self.clear_message()
                # TODO Add decode NAK command
                logger.info("## Pump sent a NAK 0x{0:X}:0x{1:X}".format(decrypted.nakcmd, decrypted.nakcode))

            if decrypted.message_type == ComDCommand.HIGH_SPEED_MODE_COMMAND:
                logger.debug("## getPumpHistory consumed HIGH_SPEED_MODE_COMMAND={0}".format(decrypted.ehs_mmode))
                if decrypted.ehs_mmode == 0:
                    pass
                else:
                    transmission_completed = True

            elif decrypted.message_type == ComDCommand.INITIATE_MULTIPACKET_TRANSFER:
                logger.info("### getPumpHistory got INITIATE_MULTIPACKET_TRANSFER")

                multi_packet_session = MultipacketSession(decrypted)

                logger.info("### session_size: {0}".format(multi_packet_session.session_size))
                logger.info("### packet_size: {0}".format(multi_packet_session.packet_size))
                logger.info("### last_packet_size: {0}".format(multi_packet_session.last_packet_size))
                logger.info("### packets_to_fetch: {0}".format(multi_packet_session.packets_to_fetch))
                logger.info("### last_packet_number: {0}".format(multi_packet_session.last_packet_number))
                logger.info("### segments_filled: {0}".format(multi_packet_session.segments_filled))


                ack_message = AckMultipacketRequestMessage(self.session, ComDCommand.INITIATE_MULTIPACKET_TRANSFER)
                bayer_ack_message = ContourNextLinkBinaryMessage(CommandType.SEND_MESSAGE, self.session, ack_message.encode())
                self.send_message( bayer_ack_message.encode() )
                self.read_response0x81()

                expected_segments = multi_packet_session.packets_to_fetch

                logger.debug("Start multipacket session")

            elif decrypted.message_type == ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION:
                logger.debug("## getPumpHistory got MULTIPACKET_SEGMENT_TRANSMISSION")

                if multi_packet_session == None:
                    logger.debug("multipacketSession not initiated before segment received")
                if multi_packet_session.payload_complete():
                    logger.debug("Multisession Complete - packet not needed")
                else:
                    if multi_packet_session.add_segment(decrypted):
                        expected_segments = expected_segments - 1

                    if multi_packet_session.payload_complete():
                        logger.debug("Multisession Complete")
                        ack_message = AckMultipacketRequestMessage(self.session, ComDCommand.MULTIPACKET_SEGMENT_TRANSMISSION)
                        bayer_ack_message = ContourNextLinkBinaryMessage(CommandType.SEND_MESSAGE, self.session, ack_message.encode())
                        self.send_message( bayer_ack_message.encode() )
                        self.read_response0x81()

                        # Save current segment
                        for x in range(len(multi_packet_session.response)):
                            segment.extend(multi_packet_session.response[x])

                        all_segments.append(bytes(segment))
                        segment = []

            elif decrypted.message_type == ComDCommand.END_HISTORY_TRANSMISSION:
                logger.debug("## getPumpHistory got END_HISTORY_TRANSMISSION")
                transmission_completed = True
            elif decrypted.message_type == ComDCommand.READ_BASAL_PATTERN_RESPONSE:
                logger.debug("## getPumpHistory got READ_BASAL_PATTERN_RESPONSE")
                all_segments.append(bytes(decrypted.response_payload)[1:])
                transmission_completed = True
            else:
                logger.warning("## getPumpHistory !!! UNKNOWN MESSAGE !!!")
                logger.warning("## getPumpHistory response.messageType: {0:x}".format(decrypted.message_type))

        if transmission_completed:
            for segment in all_segments:
                if len(segment) > 3:
                    basal_patterns = {}
                    index = 2
                    number = BinaryDataDecoder.read_byte(segment, index)
                    items = BinaryDataDecoder.read_byte(segment, index + 1)
                    logger.debug("Basal pattern: {0}, Items: {1}".format(number, items))
                    index += 2
                    for i in range (items):
                        rate = BinaryDataDecoder.read_uint32be(segment, index) / 10000.0
                        time = BinaryDataDecoder.read_byte(segment, index + 4) * 30
                        time_str = str(timedelta(minutes=time))
                        basal_patern = {
                            "rate" : rate,
                            "time_minutes" : time,
                            "time_str" : time_str,
                        }
                        basal_patterns.update({ "{0}".format(i+1) : basal_patern })
                        index += 5

                    return basal_patterns
                else:
                    return {}
        else:
            logger.error("Transmission finished, but READ_BASAL_PATTERN_RESPONSE did not arrive")

    def get_pump_basal_pattern(self):
        logger.debug("# Get Basal Pattern")
        all_basal_patterns = {}

        for i in range (1,9):
            mt_message = PumpBasalPatternRequestMessage( self.session, i)

            bayer_message = ContourNextLinkBinaryMessage( CommandType.SEND_MESSAGE, self.session, mt_message.encode() )
            self.send_message( bayer_message.encode() )
            self.read_response0x81()

            all_basal_patterns.update({NGPConstants.BASAL_PATTERN_NAME[i] : self.get_pump_basal_pattern_current_number()})

        return all_basal_patterns
