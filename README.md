# Slot Car Data Logger

Circuit python code to run the data logger device.

This code runs a Pi Pico W that runs a (flat track) slot car data logger. The device comprises a simple circuit that
measures positive and negative voltage and current, and normalizes this to a 0 - 3.3v signal for input to the Pi Pico 
on its 3 ADC inputs.

The device intermediates between a slot car track and the controller and collects data about varying controller 
current and voltage and the (mostly fixed at ~12vDC) track voltage in real time from a slot car controller 
and track supply. 

The information is useful to a driver (the person operating the controller) so that they can improve their lap times. 
Therefore the data shall be fed back to them in near realtime and retrospectively, in a way that it can easily be 
disseminated and put to use.

The feedback mechanism shall be a continuously scrolling line graph of three traces displayed in a web browser on a connected device.
It would obviously be helpful to also maintain an archive of this data for later examination.

The device is standalone and has no knowledge about the track layout, however perhaps in some later release we could
arrange a way to input track layout data to make traces more meaningful. However raw plots are expected to show 
correlations that should make the car's track position easy to discern - for example when a car starts, it's expected
to go from "zero" to maximum current and voltage very quickly.

A typical lap time is in the order of 4 - 6 seconds on a track that can have between 4 and 8 lanes. Lanes are 
color-coded by convention. Each lane could have a logger. A race can last between 5 and 15 minutes.

To collect a meaningful dataset the data shall be sampled say at 100mSec (1/10 sec) intervals or shorter (this might be adjusted 
to minimize the amount of collected data). Therefore in say a 15 minute session a single controller is 
capturing say 15 * 60 * 10 * 3 = 27,000 tuples of timestamp, value, tag. As a character string this might be 
say ~23 bytes e.g. 206656250000,0.012085,V  Total ~1/2 MByte

The design is (simplistically): read from ADC, write to sink. Where the sink could be:

 - A remotely connected (track) computer or personal laptop receiving a stream - not saving any data locally on the Pico.
 - Local filesystem on the Pico - given the volumes a single race might just be accommodated on "CIRCUITPY" without needing
   a ssd.
 - Both.

Streaming data to a remote device seems "problematic". 

The circuit python implementation of the http server does not support 
websockets. This would be the best solution. It does look like it's available with micropython https://www.donskytech.com/using-websocket-in-micropython-a-practical-example/ 

There is pub/subscribe service called MQTT - which looks like overkill.

There is a micro python redis client https://micropython-redis.readthedocs.io/en/latest/ that might be an easy port 
and could be useful - but it complicates the install by needing to install a Redis server, introduces latency
and a shim for the browser to read from Redis - not the pi. It would provide a convenient cache solution.


## Device Specifics

Notes about the hardware.

Channels:

  GP18 - external LED, low = ON  
  GP22 - Push button  
  GP26/ADC0 - Current  
  GP27/ADC1 - Controller + output voltage to track and motor  
  GP28/ADC2 - Track incoming + supply voltage  

Note: Set GP18 to output drive strength 12mA, to minimise volt-drop in the micro (PADS_BANK0: GPIOx Registers) 

Note: Worth experimenting with the SMPS mode pin (WL_GPIO1) to find out which
setting (low or high) gives the least noise in the ADC readings (with
the little test programme I got around 10 decimal variation, of a 12 bit
value, in the current zero value)

Please choose a pin to use as a program loop time indicator,
toggles from one state to another each time round the loop.

The original intention for the push button was to calibrate the zero
current value (nominal 1/2 the micro 3V3 supply) with the black output
lead disconnected, but it could also be used to calibrate the voltage
signals by setting them to an exact 12.00V.

## Design Notes


There only a push button for input (unless and until we have BT) :-( so the device needs to make some assumptions
about the WiFi network.

Tracks don't often have WiFi - so assume the owner (someone) will create a personal hotspot with a conventional name 
like: "slot-car-network*" and a conventional password "sl0tc1r" Search for this - if it's not found blink a red led, 
but continue to log data locally.
 
Assume each logger needs a unique hostname. Without BT these need to be assigned algorithmically.
No real way to match lane to a controller color but it's sensible to use this scheme.
So the code needs to look for hostname clashes and uniqueify its own name by suffixing.  

With a network connection file(s) can be opened and the ADC inputs can be started, then the web server started to
serve up the collected data.

### TODO:

Lots  
Saving files. Pain in the neck to remount the fs.  
Re integrate the led classes and button - modularize the code  
JS for plotting plot.ly say  
Use the async_button class https://circuitpython-async-button.readthedocs.io/en/latest/  
File system logging  
Run calibration when enter the state.  
Network names - fix   
BT.  
Better errors  

### Issues:

How to stream data out.  
