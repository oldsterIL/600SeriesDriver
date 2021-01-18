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
import datetime

import pickle # needed for local history export

if __name__ == '__main__':

    mt = cnl24lib.Medtronic600SeriesDriver()

    pump_status = {}

    if mt.open_device():
        logger.info("Open USB")

        try:

            mt.request_device_info()
            logger.info("CNL Device serial: {0}".format(mt.device_serial))
            logger.info("CNL Device model: {0}".format(mt.device_model))
            logger.info("CNL Device sn: {0}".format(mt.device_sn))
            mt.enter_control_mode()

            try:
                mt.enter_passthrough_mode()
                try:

                    mt.open_connection()
                    try:
                        mt.request_read_info()
                        mt.read_link_key()

                        logger.info("pump_mac: 0x{0:X}".format(mt.session.pump_mac))
                        logger.info("link_mac: 0x{0:X}".format(mt.session.link_mac))
                        logger.info("encryption key from pump: {0}".format(binascii.hexlify( mt.session.key)))

                        if mt.negotiate_channel():
                            logger.info("Channel: 0x{0:X}".format(mt.session.radio_channel))
                            logger.info("Channel RSSI Perc: {0}%".format(mt.session.radio_rssi_percent))
                            mt.begin_ehsm()
                            try:

                                mt.get_pump_time()
                                logger.info("Pump time: {0}".format(mt.pump_time))
                                logger.info("Pump time drift: {0}".format(mt.pump_time_drift))

                                # !!! Max timedelta = 10 days
                                start_date = datetime.datetime.now() - datetime.timedelta(days=5)
                                # TODO find a solution how to set the time to the nearest minute
                                # start_date = datetime.datetime.now() - datetime.timedelta(minutes=30)
                                end_date = datetime.datetime.max

                                # Sensor history = cnl24lib.HistoryDataType.SENSOR_DATA
                                # Pump history = cnl24lib.HistoryDataType.PUMP_DATA
                                history_type = cnl24lib.HistoryDataType.PUMP_DATA

                                history_info = mt.get_pump_history_info(start_date, end_date, history_type)

                                logger.info("ReadHistoryInfo Start : {0}".format(history_info.from_date))
                                logger.info("ReadHistoryInfo End   : {0}".format(history_info.to_date))
                                logger.info("ReadHistoryInfo Size  : {0}".format(history_info.length))
                                logger.info("ReadHistoryInfo Block : {0}".format(history_info.blocks))


                                history_pages = mt.get_pump_history(start_date, end_date, history_type)

                                # Dump 'history_pages' for offline parse. See 'test_history.py'
                                with open('history_data.dat', 'wb') as output:
                                   pickle.dump(history_pages, output)

                                events = mt.process_pump_history(history_pages, history_type)
                                print("# All events:")
                                for ev in events:
                                    print(ev)
                                print("# End events")


                                # # TODO Fixme
                                # # mt.get_pump_basal_pattern()
                                #
                                # # Соотношение инсулин/углеводы I:C [g]
                                # # Insulin to carb ratio
                                # ic = mt.get_bolus_wizard_carb_ratios()
                                # print(ic)
                                #
                                # # Целевой диапазон СК [mg/dL,mmol/L]
                                # # Target BG range
                                # bg_range = mt.get_bolus_wizard_targets()
                                # print(bg_range)
                                #
                                # # Фактор чувствительности к инсулину ISF [mg/dL/U,mmol/L/U]
                                # # Insulin Sensitivity Factor
                                # isf = mt.get_bolus_wizard_sensitivity()
                                # print(isf)
                                #
                                # status = mt.get_pump_status()
                                #
                                # pump_status = {
                                #     "cnl" : {
                                #         "serial"      : mt.device_serial,
                                #         "model"       : mt.device_model,
                                #         "sn"          : mt.device_sn,
                                #         "channel"     : mt.session.radio_channel,
                                #         "rssiPercent" : mt.session.radio_rssi_percent,
                                #     },
                                #
                                #     # Pump status
                                #     "pumpStatus" : {
                                #         "suspended"              : status.is_pump_status_suspended,
                                #         "bolusingNormal"         : status.is_pump_status_bolusing_normal,
                                #         "bolusingSquare"         : status.is_pump_status_bolusing_square,
                                #         "bolusingDual"           : status.is_pump_status_bolusing_dual,
                                #         "deliveringInsulin"      : status.is_pump_status_delivering_insulin,
                                #         "tempBasalActive"        : status.is_pump_status_temp_basal_active,
                                #         "cgmActive"              : status.is_pump_status_cgm_active,
                                #         "batteryLevelPercentage" : status.battery_level_percentage,
                                #         "pumpTime"               : mt.pump_time.strftime("%d-%m-%Y %H:%M:%S"),
                                #         # "pumpTimeDrift" : mt.pump_time_drift.strftime("%H:%M:%S"),
                                #     },
                                #     # Pump alert
                                #     "pumpAlert" : {
                                #         "alertOnHigh"     : status.is_plgm_alert_on_high,
                                #         "alertOnLow"      : status.is_plgm_alert_on_low,
                                #         "alertBeforeHigh" : status.is_plgm_alert_before_high,
                                #         "alertBeforeLow"  : status.is_plgm_alert_before_low,
                                #         "alertSuspend"    : status.is_plgm_alert_suspend,
                                #         "alertSuspendLow" : status.is_plgm_alert_suspend_low
                                #     },
                                #     "alert" : {
                                #         "alert"                        : status.alert,
                                #         "alertDate"                    : status.alert_date.strftime("%d-%m-%Y %H:%M:%S"),
                                #         "alertSilenceMinutesRemaining" : status.alert_silence_minutes_remaining,
                                #         "isAlertSilenceAll"            : status.is_alert_silence_all,
                                #         "isAlertSilenceHigh"           : status.is_alert_silence_high,
                                #         "isAlertSilenceLow"            : status.is_alert_silence_high_low,
                                #     },
                                #     # Sensor status
                                #     "sensorStatus" : {
                                #         "calibrating": status.is_sensor_status_calibrating,
                                #         "calibrationComplete": status.is_sensor_status_calibration_complete,
                                #         "exception": status.is_sensor_status_exception,
                                #         "calMinutesRemaining": status.sensor_cal_minutes_remaining,
                                #         "batteryLevelPercentage": status.sensor_battery_level_percentage,
                                #         "rateOfChange": status.sensor_rate_of_change,
                                #         # BGL
                                #         "bgl": status.sensor_bgl,
                                #         "bglTimestamp": status.sensor_bgl_timestamp.strftime("%d-%m-%Y %H:%M:%S"),
                                #         "trendArrow": status.trend_arrow
                                #     },
                                #     # Bolus
                                #     "bolus" : {
                                #         "delivered": status.bolusing_delivered,
                                #         "minutesRemaining": status.bolusing_minutes_remaining,
                                #         "reference": status.bolusing_reference,
                                #         "lastAmount": status.last_bolus_amount,
                                #         "lastTime": status.last_bolus_time.strftime("%d-%m-%Y %H:%M:%S"),
                                #         "lastReference": status.last_bolus_reference,
                                #         "recentWizard": status.recent_bolus_wizard,
                                #         "recentBGL": status.recent_bgl,
                                #     },
                                #     # Basal
                                #     "basal" : {
                                #         "activePattern": status.active_basal_pattern,
                                #         "activeTempPattern": status.active_temp_basal_pattern,
                                #         "currentRate": status.current_basal_rate,
                                #         "tempRate": status.temp_basal_rate,
                                #         "tempPercentage": status.temp_basal_percentage,
                                #         "tempMinutesRemaining": status.temp_basal_minutes_remaining,
                                #         "unitsDeliveredToday": status.basal_units_delivered_today,
                                #     },
                                #     # Insulin
                                #     "insulin" : {
                                #         "unitsRemaining": status.insulin_units_remaining,
                                #         "minutesOfRemaining": status.minutes_of_insulin_remaining,
                                #         "active": status.active_insulin,
                                #     },
                                # }
                                # print(pump_status)

                                logger.info("we here")

                            finally:
                                mt.finish_ehsm()
                        else:
                            logger.error("Cannot connect to the pump.")
                    finally:
                        mt.close_connection()
                finally:
                    mt.exit_passthrough_mode()
            finally:
                mt.exit_control_mode()
        finally:
            mt.close_device()
    else:
        logger.info("Error open USB")

