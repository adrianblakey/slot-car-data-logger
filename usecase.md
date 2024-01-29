# Use Case 

***Early draft***

The basic device shall be comprised of the following:  

  - Pi Pico W processor.  
  - 2 buttons.  
  - Piezo buzzer.  
  
The V1 production device shall comprise the following:

  - All of the above.  
  - A micro sdcard.  

The V2 production device shall comprise:  

  - The basic device - without the buzzer.  
  - Micro sd card.  
  - A small led display.   
  - 2 buttons.  
  - Rotary

The device shall operate in two scenarios, namely:  

  1. As a standalone device with Bluetooth connectivity that shall enable the device to be attached to say either: a phone running a generic Bluetooth client, or a track server, or both.  
  2. As a WiFi-connected client device (not as an access point) that may be attached to a track server. (Note: a local track WiFi network may or may not have a connection to the Internet ...)  
  
Operating either as a standalone or WiFi connected device, it shall be possible to capture data in realtime and read it back, either to the onboard flash or an optional SD card peripheral. If an SD card is attached it shall be detected by the software at startup (boot.py) and used in preference to the onboard flash. We assume I/O to the onbard flash shalll be quicker than I/O to an sd card. Writing data asynchonrously shall attempt to minimize any delays. (TODO backup/overflow/duplex)

The signal to start capturing data shall be the press of a button on the device, (or perhaas a button on a hi-function, next generation, connected hand controller :-)). Pressing the button a second time shall stop collection. Flashing leds shall indicate data is being collected.

On initialization the device shall detect a WiFi network and attempt to make a connection. Mutiple 
WiFi configurations (SSID, uid, password) may be saved on the device. Each configurtion shall be tried in turn to establish a connection. It shall be beneficial to keep this list to a minimum to save space and optimize search time. If the device fails to connect 
to a WiFi network the device shall disable this form of communication. 

The process for creating a WiFi configuration shall involve connecting 
a computer to the device using a USB cable and writing a file of the form wifi-*.jason to the device. There shall also be a 
default configuration on the device of: 

  - SSID: slotcar
  - uid: slotcar
  - pwd: sl0tc1r

So that the user shall be able to configure their phone as an access point to enable the logger to get a net connection. With the device now network-attached, it shall be possible to upload addtional WiFi configuration files, or other files to the flash using a Web browser interface.

The software shall detect the file system's free space size and writes shall be prevented from completely filling up the filesystem. This is important for writes to flash to prevent file system corruption.

A collection of profiles (a track/lane tuple) shall be stored on the filesystem in a file. The device shall be shipped with profiles for several UK tracks (track name and lanes). The user shall be able to select a specific profile after power on either by button presses, or by connecting a portable Bluetooth device like a phone, and using generic BT client software that provides write access to device-presented characteristics to select and display a specific profile. 

We shall also maintain in a github repo a complete collection of UK track profiles. It shall be possible to instruct the device to download track profiles from this store to the device.

The use case assumes a user shall, before they visit a specific track, they'd power up the device and select the track they are about to attend. With the device connected to the Internet, it shall update its local track description from the git repo. On arrival at the track the device shall be power up, and the initial lane and event type nominated using a Bluetooth client or button presses. 

There shall be three differnt nominations, to accelerate lane switching, namely:  

  1. Random choice - hop on any lane in no specific order.  
  2. Practice - a specific lane rotation.  
  3. Race - the track-specific lane rotation for racing - maintained in the tracks description data.  

The device may be connected to up to 2 Bluetooth clients for selecting a track profile and receiving log data output. 

The device advertises 3 BT services, namely:  

  1. Read-only, device recognition, comprising:
      
     1. NameSerial number and IP address (if attached).  
     2. Software Version.  
     3. Software name.   
  2. A read/write profile service - for display and modifying the target track and lane selection.  
  3. A notification service for receiving the device-captured track voltage, controller current and controller voltage and current data.  
     
Note: Bluetooth low energy standards and the device's python implemenatation seem to restrict the device to a maximum of 3 advertisements. Any extensions to the Bluetooth capbilities should therefore add characteristics to the profile maintenance service.

Prior to attending a specific track or at arrival at the track, the device shall be powered up by plugging in to a lane or suitable bench power supply (note: the device also has a standard micro-usb connection on the pi pico w board that will power up the device and permit serial terminal access to the python “REPL”) using the standard three color-coded banana plugs.

It’s then enabled for Bluetooth and button input.
As a Bluetooth low energy server it may be located by a conventional name of the form “lgr-nnnnnn”. This value shall be printed on the device to distinguish specific loggers from each other.

Several “free” Bluetooth client apps are available for the iPhone and Android. Download one, open it up and scan for devices. The logger shall appear in the list. Connect to it to see its 3 service advertisements. (Todo list the UUIDs)

The BLE-standard device profile service shows device information, the setting service offers writable characteristics to configure:   
  
  - Profile (track, lane)WiFi (ssid, password).  
  - The logger notification output service provides log data.  
    
Do not subscribe to the log notification service and its single characteristic unless you have use for the provided data. Its purpose is to feed data to a trackside server in preference to WiFi if there isn’t a WiFi service. We should also consider protecting this feed from eavesdropping if it's the choice of the specific user to not share it with the track and other drivers.

The configuration service offers the ability to select a specific profile. Profiles are simple track/lane pairs identified by an integer number starting at 1.

You can obtain a list of profiles from the centrally maintained file of profiles saved on GitHub at the following URL. This file will be maintained and over time shall start to differ from the stored profiles on the device. It is synchronised whenever the device has an Internet connection.

Obviously the number of UK (and foreign) tracks is large. Multiply that by lane count and identifiers can reach into the thousands. Therefore we advise setting the profile to the first lane of a specific track and use buttons (or BT) to navigate between lanes.

The buttons permit moving between profiles at power on. When the device is powered on there is a short period of time during which the 2 buttons provide the ability to switch between lanes of the currently selected track.

When the device is powered on it first tries to initiate a WiFi connection using any of the saved WiFi parameters starting with the last default settings. 
If it can make a connection it then tries to connect to a conventionally named server advertising itself using Bonjour/mdns as - “slot-car-track.local” 

If this is successful it synchronises the track configuration onto the device and sets the lane on the server and device to the first unoccupied lane. The profile id is adjusted accordingly to match the corresponding lane/track. If it can’t find a local track server it tries to connect to GitHub to synchronize the local track’s file containing track details (so it can use this data to annotate its log) hmmmm - timeout?)

If the device can’t establish a wifi connection it uses the last persisted data on the device to identify the track.
The device now permits the lane number to be adjusted using the 2 buttons on the device. 

The device flashes the lane number using the red led. The number of flashes correspond to the lane number starting by convention with the red lane as number 1. The flashes occur .5 secs apart and are repeated at 3 sec intervals. 

Default configuration of the  2 buttons is as follows:  

  1. Yellow button increments the lane number.  
  2. The red button decrements the lane number.  
     
On reaching the first lane or last lane the lane number wraps around e.g. on a four lane track decrementing lane 1 results in lane 4 being selected etc. 

If no buttons are pressed within 10 seconds the device moves out of this setting mode. This setting mode may also be cancelled by pressing both buttons simultaneously.

The device initializes all its functionality and changes the button behavior so that they now become responsible for data capture to and replay from files on the device 
After power on the button defaults to:  

  - Yellow button - toggle on/off local data capture of log data to a local timestamped file.  
  - Red button - replay the last captured log file to BT and WiFi connected readers in preference to realtime data.  
    
A track server application shall be provided that shall maintain track data such as:  
  - Length.  
  - Geographic location.  
  - Number and color of lanes.  
  - Lane rotation.  
  - Lane vectors represented in SVG so that an accurate diagram of the track may be displayed in a browser.  
  - Lane segments in hundredths on the total lap length.  
  - Lap records by class.  

The data shall be sufficient to correlate log data with the track specifics to give the data "meaning". 

(TODO - and controller and car-specific data?)

The track server application shall not need to be connected to the internet, if it is connected it shall on startup attempt to retrieve the latest track configuration data from a central track datastore maintained on github.  

If track specifics are not located on the server it shall prompt for input of track details from its startup screen. The input data shall be persisted and not need ot be reentered.
The track server shall configure 
