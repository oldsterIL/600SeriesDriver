# Driver for reading data from pumps Medtronic 600x series (640g/670g)

## What is it
This driver allows reading data from Medtronic 600x series (640/670) pumps via
blood glucose meter _Contour Next Link 2.4_ (_Contour Plus Link 2.4_).
Data is output to the console, loading data into Nightscout is NOT supported. Supported: reading the current data of the pump, reading the historical data of the sensor and the pump.

The projects are based on:
  - [decoding-contour-next-link](https://github.com/pazaan/decoding-contour-next-link) author of [Lennart Goedhart](https://github.com/pazaan) basis of the project
  - [ddguard](https://github.com/ondrej1024/ddguard) by [Ondrej Wisniewski](https://github.com/ondrej1024) important fixes
  - [600SeriesAndroidUploader](https://github.com/pazaan/600SeriesAndroidUploader) author [Lennart Goedhart](https://github.com/pazaan) data parsing, logic
  - [uploader](https://github.com/tidepool-org/uploader) author of [Tidepool Project](https://github.com/tidepool-org) data parsing, logic, documentation
  - User comments

## Current state

At the moment, this is a beta version. Unstable work is observed when reading historical data.
**Attention!** Stable reading of historical data works only when the "DEBUG" logging level is set.
I assume this is due to the timeouts for reading data from CNL.

## Plans

  - Improved stability of reading history data
  - Further parsing of historical data
  - Fix error, refactoring

## Requirement

The code is written in python3 and tested on a _Raspberry Pi Zero_ using [PyCharm Professional](https://www.jetbrains.com/pycharm/).
Installing the required libraries:

`sudo apt-get install python3-pip libudev-dev libusb-1.0-0-dev liblzo2-dev
sudo -H pip3 install hidapi astm crc16 python-lzo PyCrypto python-dateutil pytz
`
Run: `python3 main.py`