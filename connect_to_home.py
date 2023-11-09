import network
import os
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm = 0xa11140)
wlan.connect("FRITZ!Box 7530 YM","73119816833371417369")