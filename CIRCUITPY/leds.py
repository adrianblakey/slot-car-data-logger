import board
import digitalio
import time

led = digitalio.DigitalInOut(board.LED)
board_led = digitalio.DigitalInOut(board.GP18)
led.direction = digitalio.Direction.OUTPUT
board_led.direction = digitalio.Direction.OUTPUT
i = 0
while True:
    i += 1
    print('looper' + str(i) + '\n')
    board_led.value = False
    led.value = True
    time.sleep(0.5)
    board_led.value = True
    led.value = False
    time.sleep(0.5)