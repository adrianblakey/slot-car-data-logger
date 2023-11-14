# Slot Car Data Logger

This repo contains the design and firmware of a slot car data logger. This is a device that should be of interest to serious slot 
car racers who are interested in gaining greater insight into their own performance and the performance of their car(s) and controller(s). It does this by measuring the volatge and current over time and saves and graphs the values.

The data logger device comprises a voltage and currrent measuring circuit that provides signals to a Raspberry Pi Pico W. These three signals are fed to 3 of the Pi Pico analog to digital (ADC) inputs on pins 26, 27 and 28. Micropython code running on the Pi reads these values and writes them to disk, bluetooth and the Web on a WiFi connection. 

TThe voltages are the track voltage - usually a fairly constant 12+ vDC, and the variable controller output voltages (sent to the car). The current is the flow to the car when it is driving forward and from the car under braking (usually quite small).

The device passively intermediates between a slot car track and the controller and collects data about varying controller 
current and voltage and the (conventionally fixed at ~12vDC) track voltage in real time from a slot car controller 
and track supply. 

The information is useful to a driver (the person operating the controller) so that they can improve their lap times. 
Therefore the data shall be fed back to them in near realtime and retrospectively, in a way that it can easily be 
disseminated and put to use.

The feedback mechanism shall be a continuously scrolling line graph of three traces displayed in a web browser on a connected device.
It would obviously be helpful to also maintain an archive of this data for later examination.

The device is standalone and has no knowledge about the track layout. An obvious improvement 
would be facilitated if all track information (number of lanes, lane colors,
lap length, lap topology e.g. 16' straight, 120 degree corner inside radius 1' ...) was available say 
from a conventionally named local or remote web server, so that make traces could be more meaningful.

However raw plots are expected to show 
correlations that should make the car's track position easy to discern - for example when a car starts, it's expected
to go from "zero" to maximum current and voltage very quickly. In a later release we could consider some sort of 
graph markup to provide the missing semantics.

A typical lap time is in the order of 4 - 6 seconds on a track that can have between 4 and 8 lanes. Lanes are 
color-coded by convention. Each lane could have a logger. A race can last between 5 and 15 minutes.

To collect a meaningful dataset the data shall be sampled say at 100mSec (1/10 sec) intervals or shorter (this might be adjusted 
to minimize the amount of collected data). Therefore in say a 15 minute session a single controller is 
capturing say 15 * 60 * 10 * 3 = 27,000 tuples of timestamp, value, tag. As a character string this might be 
say ~23 bytes e.g. 206656250000,0.012085,V  Total ~1/2 MByte

The design is (simplistically): read from the ADC's, write to a sink. Where the sink could be:

 1. A remotely connected (track) computer or personal laptop receiving a stream - not saving any data locally on the Pico.  
 2. Local filesystem on the Pico - given the volumes a single race might just be accommodated on "CIRCUITPY" without needing
   a ssd.  
 3. Both.  

Circuit Python limits persistent storage for both code and data to 1MBytes, therefore it's not really practical to store data locally, and in any event it
would still need to be copied off the device. Therefore, wifi is used to stream data in real-time to the browser using server send events - a simple mechanism implemented in the Circuit Python web server.

## Device Specifics

Notes about the hardware.

Channels:

  GP16      - Push button - black  
  GP17      - External red LED, low = ON  
  GP18      - External yellow LED, low = ON  
  GP21      - Piezo sound - (low volume sound output in the range 200Hz - 4KHz)  
  GP22      - Push button - yellow
  GP26/ADC0 - Current drawn by the motor through the hand controller  
  GP27/ADC1 - Output voltage to track and motor from the hand controller  
  GP28/ADC2 - Track incoming supply voltage  

Notes: 

 1. Set GP18 to output drive strength 12mA, to minimise volt-drop in the micro (PADS_BANK0: GPIOx Registers)  

 2. Worth experimenting with the SMPS mode pin (WL_GPIO1) to find out which
setting (low or high) gives the least noise in the ADC readings (with
the little test programme I got around 10 decimal variation, of a 12 bit
value, in the current zero value)  

 3. Please choose a pin to use as a program loop time indicator,
toggles from one state to another each time round the loop.  

 4. The original intention for the yellow push button was to calibrate the zero
current value (nominal 1/2 the micro 3V3 supply) with the black output
lead disconnected, but it could also be used to calibrate the voltage
signals by setting them to an exact 12.00V.  

## Testing

Connections:

  White +ve supply
  Red -ve supply
  Black + output to motor

Simplest test: connect white & red 4mm banana plugs of the logger to the PSU & vary the power supply voltage from 8V to 18V. The supply voltage signal should vary, the black output should read zero & the current a mid range value corresponding to zero current.

Next level: connect the controller to the 4mm sockets, operate the trigger & now the black output signal should vary.

Final level: now add a motor (motor+ to the 4mm black banana from the logger, motor- to PSU - with 4mm red banana from logger) and operate the trigger, the current signal should now vary as well. But it will be small as the range is +/- 50A.

## Connecting to WiFi

Most tracks do not have WiFi or access to the internet, therefore you'll need to provision something yourself. If you have a decent cellular connection you can try setting up your phone as a personal hotspot.

The settings.toml file is coded to locate a WiFi network conventionally named "slotcar" with a password of "slot-car". Doing this on an iPhone, an 8 character minimum password must be set, so it's not possible to create an unprotected WiFi AP as a Apple iPhone hotspot.

So edit the "Settings->General->About->Name" to "slotcar" and then navigate to: "Settings->Personal Hotspot->Wi-Fi Password" and set it to "slot-car" In the personal hotspot set on "Allow Others to Join" and "Maximum Compatibility" This second setting is important because the radio in the Pi only operates on 2.4GHz

Once you've done this leave the Personal Hotspot open and wait for the logger to connect. Note: every time it fails to make a WiFi connection it reboots and plays a tune. Therefore you can plug it in and play with the WiFi settings until it successfully connects.

Of course this means there can only be a single network names "slotcar" in the vicinity and everyone's logger shall connect to it. However, without an easy way to set each specific-logger's preferred AP name, (using Bluetooth?) we are stuck with this.

Another alternative would be to have a WiFi access point stationed permanently at the track with it obtaining its access to the Inet from a personal hotspot. Although this is really not much better than the previous solution - except perhaps it might offer better range.

 The use case would be: someone would "volunteer" to provide Inet access to the Ap, by setting their phone to a conventional name, the Ap then would be paired with the hot spot and the loggers would attach to the Ap. An AP with two radios and appropriate software (like OpenWRT) is needed to arrange this. It would broadcast its SSID as "slotcar" (slot-car) and there would be another conventional name for the hotspot for the AP to connect to - say "slot-car-hotspot"``
 
 
 ## Design Notes

Use the yellow button for input, the black for navigation. Perhaps Adafruit will provide Bluetooth and then
it can be used for configuration. https://github.com/adafruit/circuitpython/issues/7693

Use the piezo for feedback. Try and obey some UI guidelines for this: https://uxplanet.org/dos-and-don-ts-of-sound-in-ux-766178f1ae95

Tracks don't often have WiFi - so assume the owner (someone) will create a personal hotspot with a conventional name 
like: "slot-car-network*" and a conventional password "sl0tc1r" Search for this - if it's not found blink a red led, 
and give up. The code uses the google chaart library that has to have an internet connection. Replacing this with a locally-cached
javascript charts library might be a workaround.
 
Input the number of lanes and my lane number on a short button press.

With a network connection file(s) can be opened and the ADC inputs can be started, then the web server started to
serve up the collected data.

## Getting Running

The Pi is running the latest release (8.2.3) of Circuit Python, which is a derivative of micro python. More about it here: https://docs.circuitpython.org/en/latest/docs/index.html The code depends on various Adafruit libraries that are updated using the "circup" utility.

With a modern version of Windows (>= 10) you should be able to simply plug the board into the computer using a USB cable and it'll magically appear as say the D: disk, and named CIRCUITPY - see https://learn.adafruit.com/welcome-to-circuitpython/the-circuitpy-drive This also works for Linux and MacOS.

Older Windows releases need drivers installed - read this: https://learn.adafruit.com/welcome-to-circuitpython/windows-7-and-8-1-drivers

Use the Windows file manager to open the CIRCUITPY folder. In it you'll find several important files, namely:

  - code.py            - the conventionally named "main" executable that is started by CP after boot. Just calls the statemachine.  
  - connectedclient.py - webserver connection state  
  - function.py        - free functions that are not bound to classes. Functions run the buttons, classes have too much encapsulation.
  - led.py             - a class that represents a led  
  - ledcontrol.py      - settings to turn a led on/off  
  - log.py             - controls the logging, there is a variable in settings.toml that controls the loglevel (DEBUG, INFO ... ERROR)  
  - settings.toml      - environment variables to connect to WiFi etc.  
  - statemachine.py    - a class that drives the processing of the code from one state to the next  
  - track.py           - represents the track we are on and the lane we are running on (later might want more details)  
  - tune.py            - couple of classes to play tunes on the piezo  
  - webserver.py       - runs the http server

There are some directories too - such as:

  - lib - holds support libraries  
  - static - html files
  - js - javascript libraries
  

Use an editor (such as Notepad++ https://notepad-plus-plus.org/downloads/) and make two changes to settings.toml. Comments in this file are preceded by a "#" - you'll see it contains the SSID and password for WiFi.

More about it here: https://docs.circuitpython.org/projects/httpserver/en/latest/examples.html

If you have not attached a serial port to the REPL (see below) you also might want to change the LOGLEVEL to "ERROR". Note the double quotes are important leaving them out will make the code think it's a number not a string.

Look at your WIFi Access point and transcribe your SSID/password into the settings file, replacing the values I have set for my own network. These will need to be standardized for actual use.

The file code.py is by convention run by Circuit Python which is installed as a boot loader/primitive operating system on the Pi and is what makes the Pi look like another Windows drive. Reinstalling Circuit Python is done by holding the reset button on the Pi while plugging in the USB - don't do that unless you really want to copy a new version of Circuit Python to the logger.

If you unplug the USB and plug it back in again the "firmware" python code will run. 

On startup once the device has got past the WiFi validation it flashes the leds and sounds a little jingle and then does a hi/lo beep to prompt for the number of lanes. 

Short presses on the yellow button represent and accumulating number. A log (>.5sec) press inputs the accumulated number. You must input between 4 and 8 for the number of track lanes. If the values is outside this range you get an error beep.

With the lane info input an attempt is made to re-connect to your WiFi network, grab an IP address, and broadcast its name as "logger-[lane-color].local" to you home wifi network.

It'll then wait for a connection from a browser. 

Open a browser on another computer attached to Wifi - best if it's Chrome. In the command line type: logger-red.local

With a bit of luck you'll see a simple web page - with a link on it, if you do not hit the link the page will redirect after 4 seconds to the same link namely: http://logger-red.local/client and should display a line chart which is continuously updated, and some buttons that refer to databases created in the browser. The databases delete button works - the chart does not, this is a "todo" item.

If you want to see some logging info in the browser - hit F12 in the browser and look at the console - it should show some logging info.

If the browser will not connect to the logger by name try using names of the form:

   "logger-[lane-color].local" 
   
Start with the conventional lowest lane color: e.g. "logger-red.local" and keep going with "logger-white.local". If this does not work -try without the ".local" suffix.

If the browser can not find the logger by name you'll need to find it by IP address or use a Bonjour browser. 

To find its IP address open a command prompt and run the arp command - read this: https://support.pelco.com/s/article/How-to-use-an-arp-table-to-fin-IP-addresses?language=en_US

The arp -a command will list all the devices on you network by MAC and IP address - there will only be say three - the Pi, the WiFi AP and you computer. Type the most likely into the browser. For example my network is 192.168.178 and the Pi shows up as: http://192.168.178.89/client A lot of consumer WiFi networks are on the 192.168.1 network - with the AP on the address 192.168.1.1. The DHCP server might run on say 192.168.1.100 and dole out ip addresses above 100.

You can also try to find it using "Bonjour". Bonjour is a simple broadcast name service invented by Apple. You might have to install it from here: https://developer.apple.com/bonjour/ The Pi broadcasts its name on the WiFi network using this technology, and most WiFi Ap's have it installed.

You can also connect to the Python console on the Pi (also called REPL) read this: https://learn.adafruit.com/welcome-to-circuitpython/advanced-serial-console-on-windows to see what it's doing.

Once you have a TTY running and attached to the REPL, you'll see it prints out "DEBUG" statements to show what it's doing. You can kill and restart the code.py program by: ctl-C and ctl-D (that is hold the ctrl key down and press c or d) ctl-C kills the program, ctl-D tries a restart. It's re-runnable. You can also type various commands into the REPL when the code is halted to debug the code.

The code is easy to understand: https://github.com/adrianblakey/slot-car-data-logger/blob/main/CIRCUITPY/code.py

Basically:

  - Sets up a temporary, no name WiFi connection.  
  - Prompts for button input to capture number of track lanes, and then the lane you are running on.  
  - Uses this info to create a unique server network name.  
  - Starts a Web server.  
  - Runs an infinite loop.  
  - The first browser interaction causes some javascript to be downloaded to the browser which opens a connection to start the Pi sending the sensor values.  
  - The server loops sending ADC values to the browser.   

### TODO:

There is always more to do - however it's limited by the amount of memory. We are already very close to using all there is and some optimizations have been made.

 1. Remotely turn on debugging and save a debug log to the file system, rotate and erase it. Access from a web page.
 2. Web page to control the browser databases - delete and chart offline.
 3. A standalone client to capture data to a file on the host - wget/curl - an app./webserver to render it.  
 4. Try a different/better js chart library and try to get it to scroll smoothly. Google is not open source and needs an Inet connection.  
 5. Test mode - where some known dataset is displayed.  
 6. Calibration - not just on startup but controlled say on some specific (long) button press.  
 7. Track and lane data read from a host.  
 8. Bluetooth configuration.
 9. Some refinement of the sounds to make it clear what state things are in. 

### Use Case

 1. Turn up at a specific track 
    How:
      Prior to visit - power logger.
      Add track by: downloadiong track or editing track database or using bluetooth app
      Specify a specific track to use
 2. Plug in to a specific lane
 3. Intermittently run logger
 4. Change lane ...
 5. Review log data. Annotate data.
 6. Erase or archive log data