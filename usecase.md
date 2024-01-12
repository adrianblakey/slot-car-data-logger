# Use Case 

***Early draft***

The basic device shall comprise:
Pi Pico W processor.2 buttonsPiezo buzzerThe V1 production device shall comprise:All of the aboveMicro sdcard
The V2 production device shall comprise:
The basic device - without the buzzerMicro sd cardA small led display2 buttonsRotary
The device shall work in three modes, namely:as a standalone device.A Bluetooth-connnected device that may be attached to a track serverA WiFi-connected device that may be attached to an internet-connected track server.
As a standalone device and a connected device data shall be read from and written to, either the onboard flash or an optional SD card peripheral. If an sd card is attached it shall be detected by the software at startup and used in preference to the onboard flash. 
If data is written to flash, the software shall detect the file system's free space size and writes shall be prevented from completely filling up the filesystem.
A collection of profiles (Track/lane tuple) shall be stored on the filesystem as or flash)
The device shall be shipped with profiles for all UK tracks (track name and lanes). The user shall be able to select a specific profile after power on either by button presses, or by connecting a portable Bluetooth device like a phone, and using generic BT client software that provides write access to device-presented characteristics to select and display a specific profile.
The device may be connected to up to 2 Bluetooth clients for selecting a track profile and receiving log data output. The device advertises 3 BT services, namely:
Read-only, device recognition, comprisingNameSerial number and IP address (if attached)Software VersionSoftware name.Read/write of the profile (track/lane) setting and display.Notification of log data (track voltage, controller voltage, controller current)Bluetooth low energy standards restrict the device to a maximum of 3 advertisements. Any extensions should add characteristics to the profile maintenance service.
Prior to attending a specific track or at arrival at the track, the device shall be powered up by plugging in to a lane or suitable bench power supply (note: the device also has a standard micro-usb connection on the pi pico w board that will power up the device and permit serial terminal access to the python “REPL”) using the standard three color-coded banana plugs.
It’s then enabled for Bluetooth and button input.
As a Bluetooth low energy server it may be located by a conventional name of the form “lgr-nnnnnn”. This value shall be printed on the device to distinguish specific loggers from each other.

Several “free” Bluetooth client apps are available for the iPhone and Android. Download one, open it up and scan for devices. The logger shall appear in the list. Connect to it to see its 3 service advertisements. (Todo list the UUIDs)
The BLE-standard device profile service shows device information, the setting service offers writable characteristics to configure:
Profile (track, lane)WiFi (ssid, password)
The logger notification output service provides log data.
Do not subscribe to the log notification service and its single characteristic unless you have use for the provided data. Its purpose is to feed data to a trackside server in preference to WiFi if there isn’t a WiFi service.
The configuration service offers the ability to select a specific profile. Profiles are simple track/lane pairs identified by an integer number starting at 1.
 You can obtain a list of profiles from the centrally maintained file of profiles saved on GitHub at the following URL. This file will be maintained and over time shall start to differ from the stored profiles on the device. It is synchronised whenever the device has an Internet connection.
Obviously the number of UK (and foreign) tracks is large. Multiply that by lane count and identifiers can reach into the thousands. Therefore we advise setting the profile to the first lane of a specific track and use buttons (or BT) to navigate between lanes.
The buttons permit moving between profiles at power on. When the device is powered on there is a short period of time during which the 2 buttons provide the ability to switch between lanes of the currently selected track.
When the device is powered on it first tries to initiate a WiFi connection using any of the saved WiFi parameters starting with the last default settings. 
If it can make a connection it then tries to connect to a conventionally named server advertising itself using Bonhour/mdns as - “slot-car-track.local” 
If this is successful it synchronises the track configuration onto the device and sets the lane on the server and device to the first unoccupied lane. The profile id is adjusted accordingly to match the corresponding lane/track. If it can’t find a local track server it tries to connect to GitHub to synchronize the local track’s file containing track details (so it can use this data to annotate its log) hmmmm - timeout?)
If the device can’t establish a wifi connection it uses the last persisted data on the device to identify the track.
The device now permits the lane number to be adjusted using the 2 buttons on the device. 
The device flashes the lane number using the red led. The number of flashes correspond to the lane number starting by convention with the red lane as number 1. The flashes occur .5 secs apart and are repeated at 3 sec intervals. 
Default configuration of the  2 buttons is as follows:
Yellow button increments the lane number.The red button decrements the lane number.
On reaching the first lane or last lane the lane number wraps around e.g. on a four lane track decrementing lane 1 results in lane 4 being selected etc. 
If no buttons are pressed within 10 seconds the device moves out of this setting mode. This setting mode may also be cancelled by pressing both buttons simultaneously.
The device initializes all its functionality and changes the button behavior so that they now become responsible for data capture to and replay from files on the device 
After power on the button default to:
Yellow button - toggle on/off local data capture of log data to a local timestamped file.Red button - replay the last captured log file to BT and WiFi connected readers in preference to realtime data.
A track server application shall be provided that shall maintain track data such as:
LengthGeographic location.Number and color of lanes.Lane rotationLane vectors represented in SVG so that an accurate diagram of the track may be displayed in a browser.Lane segments in hundredths on the total lap lengthLap records by classetc.
The data shall be sufficient to correlate log data with the track specifics to give the data "meaning". 
The track server application shall not need to be connected to the internet, if it is connected it shall on startup attempt to retrieve the latest track configuration data from a central track datastore maintained on github.
If track specifics are not located on the server it shall prompt for input of track details from its startup screen. The input data shall be persisted and not need ot be reentered.
The track server shall configure 
