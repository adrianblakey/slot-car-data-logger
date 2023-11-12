# Copy from host to device
#mpremote connect /dev/cu.usbmodem2101 cp ./apple-touch-icon.png :templates/apple-touch-icon.png

# Backup device

mpremote connect /dev/cu.usbmodem2101 cp :main.py ~/slot-car-data-logger/main.py