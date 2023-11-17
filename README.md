# Slot Car Data Logger

This repo contains the design and firmware of a slot car data logger. This is a device that should be of interest to serious slot 
car racers who are interested in gaining greater insight into their own performance and the performance of their car(s) and controller(s). It does this by measuring the volatge and current over time and saves and graphs the values.

The data logger device comprises a voltage and currrent measuring circuit that provides signals to a Raspberry Pi Pico W. These three signals are fed to 3 of the Pi Pico analog to digital (ADC) inputs on pins 26, 27 and 28. Micropython code running on the Pi reads these values and writes them to disk, bluetooth and the Web on a WiFi connection. 

The voltages are the track voltage - usually a fairly constant 12+ vDC, and the variable controller output voltages (sent to the car). The current is the flow to the car when it is driving forward and from the car under braking (usually quite small).

The device passively intermediates between a slot car track and the controller and collects data about varying controller 
current and voltage and the (conventionally fixed at ~12vDC) track voltage in real time from a slot car controller 
and track supply. 

The information is useful to a driver (the person operating the controller) so that they can improve their lap times. 
Therefore the data can be fed back to them in near realtime and retrospectively, in a way that it can easily be 
disseminated and put to use.

The feedback mechanism is be a continuously scrolling line graph of three traces displayed in a web browser on a connected device.

The device is standalone and has no knowledge about the track layout. An obvious improvement 
would be track knowledge e.g. number of lanes, lane colors,
lap length, lap topology e.g. 16' straight, 120 degree corner inside radius 1'. It would also be important to know where the start finish lane was 
located. On tracks where this is implemented a a dead strip this can be correlated to a regular dip to near zero in the current data.
Furthermore if the track data was stored centrally on a web server, it could be downloaded onto the device on startup or before racing. 
Correlating the track topographywith traces would make traces semantically meaningful.

However raw plots are expected to show 
correlations that should make the car's track position easy to discern - for example when a car starts, it's expected
to go from "zero" to maximum current and voltage very quickly. In a later release we could consider some sort of 
graph markup to provide the missing semantics.

A typical lap time is in the order of 3 - 6 seconds on a track that can have between 4 and 8 lanes. Lanes are 
color-coded by convention. Each lane could have a logger. A race can last between 5 and 15 minutes.

To collect a meaningful dataset the data shall be sampled say at 10mSec (10, 1 thousandths of sec) intervals or slightly longer (this might be adjusted 
to minimize the amount of collected data). Therefore in say a 15 minute session a single controller is 
capturing say 15 * 60 * 10 * 3 = 27,000 tuples of timestamp, value, tag. As a character string this might be 
say ~23 bytes e.g. 206656250000,0.012085,V  Total ~1/2 MByte

The design is (simplistically): read from the ADC's, and written to a sink. Where the sink can be:

 1. A remotely connected web browser.  
 2. Local filesystem on the Pico on the flash or sdcard.
 3. Bluetooth.  

There is limited flash storage to store data locally, the code does not fully populate the store to guard against filesystems issues.
And in any event it might still need to be copied off the device. A WiFi connection to a browser is used to stream data in real-time
using websockets - a simple mechanism implemented in the Microdot web server.

## Device Specifics

Notes about the hardware.

Channels:

  GP16      - Push button - black  
  GP17      - External red LED, low = ON  
  GP18      - External yellow LED, low = ON 
  GP20      - Piezo sound 
  GP21      - Piezo sound (inverted) - (low volume sound output in the range 200Hz - 4KHz)  
  GP22      - Push button - yellow
  GP26/ADC0 - Current drawn by the motor through the hand controller  
  GP27/ADC1 - Output voltage to track and motor from the hand controller  
  GP28/ADC2 - Track incoming supply voltage 
  GP29/ADC3 - not used - mcu power

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

Most tracks do not have WiFi or access to the internet, therefore you'll need to provision something yourself. 
If you have a decent cellular connection you can try setting up your phone as a personal hotspot.

The wifi.json file can be edited to contain the local wifi connection settings. Alternatively any file named wifi-*.json 
can contain a wifi setting all of which are searched on startup. If no connection is established the code does not 
start a web server. 

The IP address of the connection is put in the BT device information by appending it to front of the conventional 
Firmware Revision String bluetooth characteristic of the Service Device Information.

You can also consider setting up your own WiFi network on your phone. On an iPhone 
edit the "Settings->General->About->Name" to "slotcar" and then navigate to: "Settings->Personal Hotspot->Wi-Fi Password" and set it to "slot-car" In the personal hotspot set on "Allow Others to Join" and "Maximum Compatibility" This second setting is important because the radio in the Pi only operates on 2.4GHz

Once you've done this leave the Personal Hotspot open and wait for the logger to connect. Note: every time it fails to make a WiFi connection it reboots and plays a tune. Therefore you can plug it in and play with the WiFi settings until it successfully connects.

Of course this means there can only be a single network names "slotcar" in the vicinity and everyone's logger shall connect to it. However, without an easy way to set each specific-logger's preferred AP name, (using Bluetooth?) we are stuck with this.

Another alternative would be to have a WiFi access point stationed permanently at the track with it obtaining its access to the Inet from a personal hotspot. Although this is really not much better than the previous solution - except perhaps it might offer better range.

 The use case would be: someone would "volunteer" to provide Inet access to the Ap, by setting their phone to a conventional name, the Ap then would be paired with the hot spot and the loggers would attach to the Ap. An AP with two radios and appropriate software (like OpenWRT) is needed to arrange this. It would broadcast its SSID as "slotcar" (slot-car) and there would be another conventional name for the hotspot for the AP to connect to - say "slot-car-hotspot"``
 
 
 ## Design Notes

Use the yellow button for toggling the collection of data to a local log file, the black for toggling between
playback of the latest log file and relatime data. 

The piezo is only used to play a little tune at startup. Despite doubling its volume by inverting the second pin 
to which it's connected, its sound output is not really loud enough 
to overcome ambient noise at the track 
for feedback. 

Tracks don't often have WiFi. There is commented out code to stream data to Bluetooth, however this will require a 
graphing client. There are different ways to do this, namely:

  1. Stream data over the BT client to a local (or remote) server on a local network that may or may not 
  be connected to the Inet, and display it from a Web server running on it.
  2. Use experimental browser extensions to connect to BT and display data in a browser
  - however the browser will still need a network connection.
 
Input the number of lanes and my lane number on a short button press.

With a network connection file(s) can be opened and the ADC inputs can be started, then the web server started to
serve up the collected data.

## Getting Running

The Pi is running the latest release (1.21) of MicroPython. More about it here: https://projects.raspberrypi.org/en/projects/get-started-pico-w/1 The code depends on various MicroPython libraries that are updated using the mip utility.

With a modern version of Windows (or MacOS or Linux) you can plug the board into the computer using a USB cable and talk to it as a serially connected USB device.

Use the Thonny IDE https://thonny.org/ to connect and access the device.

There are several python files on the disk and some directories.

There are some directories too - such as:

  - lib - holds support libraries  
  - static - html files
  - js - javascript libraries
  

Use the Thonny editor to create a wifi.json file.
Start the code by ctl-D
Debugging statements appear in the log.
It'll display the IP address to which it's connected. Point a browser at this address.
   

### TODO:

There is always more to do - however it's limited by the amount of memory. We are already very close to using all there is and some optimizations have been made.

 1. Remotely turn on debugging and save a debug log to the file system, rotate and erase it. Access from a web page.
 2. Save data in the browser, replay in the browser, delete browser database
 3. A standalone client to capture data to a file on the host - wget/curl - an app./webserver to render it.
 4. Export log files to a server page - both http and bluetooth
 5. Replay exported log files on a server.
 6. Alter the graphing parameters to slow down/expand the x scale.  
 7. Calibration - not just on startup but controlled say on some specific (long) button press.  
 8. Track and lane data read from a host.
 9. GPS module to determine the track from the track database.
 10. Tracks stored on host in track database.
 11. Download the current track as json from track database.
 12. Select a specific locally saved log file, delete a log file.
 13. Annotate a log file: car/track/controller (settings)
 14. BT client to control the app.
 15. BT client to graph rt and saved file.
 16. Mount sd in boot and save data to a sd card.
 

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