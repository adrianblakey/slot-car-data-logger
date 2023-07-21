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

Data is streamed to the browser using server send events - a simple mechanism implemented in the Circuit Python web server.

## Device Specifics

Notes about the hardware.

Channels:

  GP18      - External LED, low = ON  
  GP22      - Push button  
  GP26/ADC0 - Current drawn by the motor through the hand controller  
  GP27/ADC1 - Output voltage to track and motor from the hand controller  
  GP28/ADC2 - Track incoming supply voltage  

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

### Getting Running

The Pi is running the latest release (8.2.0) of Circuit Python, which is a derivative of micro python. More about it here: https://docs.circuitpython.org/en/latest/docs/index.html

With a modern version of Windows (>= 10) you should be able to simply plug the board into the computer using a USB cable and it'll magically appear as say the D: disk, and named CIRCUITPY - see https://learn.adafruit.com/welcome-to-circuitpython/the-circuitpy-drive

Older Windows releases need drivers installed - read this: https://learn.adafruit.com/welcome-to-circuitpython/windows-7-and-8-1-drivers

Use the Windows file manager to open the CIRCUITPY folder. In it you'll find two important files, namely:

  - code.py  
  - settings.toml  

There are some directories too - such as lib and static - you can ignore these.

Use an editor (such as Notepad++ https://notepad-plus-plus.org/downloads/) and make two changes to settings.toml. Comments in this file are preceded by a "#" - you'll see it contains the SSID and password for WiFi.

More about it here: https://docs.circuitpython.org/projects/httpserver/en/latest/examples.html

Look at your WIFi Access point and transcribe your SSID/password into the settings file, replacing the values I have set for my own network. These will need to be standardized for actual use.

The file code.py is by convention run by Circuit Python which is installed as a boot loader/primitive operating system on the Pi and is what makes the Pi look like another Windows drive. Reinstalling the Circuit Python is done by holding the reset button on the Pi while plugging in the USB - don't do that :-)

If you unplug the USB and plug it back in again the code will run and attempt to connect to your WiFi network, grab an IP address, and broadcast its name as "logger-red.local" to you home wifi network.

It'll then wait for a connection from a browser. 

Open a browser on another computer attached to Wifi - best if it's Chrome. In the command line type: logger-red.local

With a bit of luck you'll see a simple web page - with a link on it, if you do not hit the link the page will redirect after 4 seconds to the same link namely: http://logger-red.local/client and should display a line chart which is continuously updated.

If you want to see some logging info in the browser - hit F12 in the browser and look at the console - it should show some logging info.

If the browser will not connect to the logger by name try the names "logger-whi.local" and "logger-red" and "logger-whi" (without the local suffix).

If the browser can not find the logger by name you'll need to find it by IP address or use a Bonjour browser. 

To find its IP address open a command prompt and run the arp command - read this: https://support.pelco.com/s/article/How-to-use-an-arp-table-to-fin-IP-addresses?language=en_US

The arp -a command will list all the devices on you network by MAC and IP address - there will only be say three - the Pi, the WiFi AP and you computer. Type the most likely into the browser, e.g. http://192.168.178.89/client

You can also try to find it using "Bonjour" Bonjour is a simple broadcast name service invented by Apple. You might have to install it from here: https://developer.apple.com/bonjour/ The Pi broadcasts its name on the WiFi network using this technology, and most WiFi Ap's have it installed.

You can also connect to the Python console on the Pi (also called REPL) read this: https://learn.adafruit.com/welcome-to-circuitpython/advanced-serial-console-on-windows to see what it's doing.

Once you have a TTY running and attached to the REPL, you'll see it prints out "DEBUG" statements to show what it's doing. You can kill and restart the code.py program by: ctl-C and ctl-D (that is hold the ctrl key down and press c or d) ctl-C kills the program, ctl-D tries a restart. It's rerunnable. You can also type various commands into the REPL when the code is halted to debug the code.

The code is easy to understand: https://github.com/adrianblakey/slot-car-data-logger/blob/main/CIRCUITPY/code.py

Basically:

  - Sets up the WiFi connection https://github.com/adrianblakey/slot-car-data-logger/blob/main/CIRCUITPY/code.py#L133  
  - Starts a Web server https://github.com/adrianblakey/slot-car-data-logger/blob/main/CIRCUITPY/code.py#L242  
  - Runs an infinite loop https://github.com/adrianblakey/slot-car-data-logger/blob/main/CIRCUITPY/code.py#L679  
  - Sends the ADC values to the browser https://github.com/adrianblakey/slot-car-data-logger/blob/main/CIRCUITPY/code.py#L221  
  - Lots of magic done in the browser https://github.com/adrianblakey/slot-car-data-logger/blob/main/CIRCUITPY/code.py#L262  

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
