#!/bin/bash -x

# Copy from host to device
#mpremote connect /dev/cu.usbmodem2101 cp ./apple-touch-icon.png :templates/apple-touch-icon.png

# Backup device

#mpremote connect /dev/cu.usbmodem2101 cp :main.py ~/slot-car-data-logger/main.py

foo=`mpremote connect /dev/cu.usbmodem2101 ls | grep log`
#echo $foo

for var in $foo; do
    if grep -q '.log' <<<"$var"; then
        var="${var/$'\r'/}"
        mpremote connect /dev/cu.usbmodem2101 cp :$var ~/slot-car-data-logger/$var
    fi

done