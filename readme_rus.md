# Драйвер для чтения данных с помп Medtronic 600х серий (640g/670g)

## Что это
Этот драйвер позволяет читать данные из помп Medtronic 600х серий (640/670) через 
глюкометр _Contour Next Link 2.4_ (_Contour Plus Link 2.4_). 
Данные выводятся в консоль, загрузка данных в Nightscout НЕ поддерживается. 
Поддерживается: чтение текущих показаний помпы, чтение исторических данных сенсора и помпы.  

В основе лежат проекты:
 - [decoding-contour-next-link](https://github.com/pazaan/decoding-contour-next-link) автор [Lennart Goedhart](https://github.com/pazaan) основа проекта
 - [ddguard](https://github.com/ondrej1024/ddguard) автор [Ondrej Wisniewski](https://github.com/ondrej1024) важные исправления
 - [600SeriesAndroidUploader](https://github.com/pazaan/600SeriesAndroidUploader) автор [Lennart Goedhart](https://github.com/pazaan) парсинг данных, логика работы
 - [uploader](https://github.com/tidepool-org/uploader) автор [Tidepool Project](https://github.com/tidepool-org) парсинг данных, логика работы, документация
 - Комментарии пользователей

## Текущее состояние

В данный момент это бета версия.   

## Планы

 - Улучшение стабильности чтения исторических данных
 - Парсинг исторических данных
 - Исправление ошибок, рефакторинг

## Требование

Код написан на python3 и тестировался на _Raspberry Pi Zero_ с использованием [PyCharm Professional](https://www.jetbrains.com/pycharm/). 
Установка необходимых библиотек:

```bash
sudo apt-get install python3-pip libudev-dev libusb-1.0-0-dev liblzo2-dev
sudo -H pip3 install hidapi astm crc16 python-lzo PyCrypto python-dateutil pytz
```
Запуск: 
```bash
python3 main.py
```
