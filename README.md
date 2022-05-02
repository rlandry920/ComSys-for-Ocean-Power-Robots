# Communication System for Ocean Power Robots

## Table of Contents

- [Overview](#overview)

  - [Installation](#installation)

  - [Usage](#usage)

- [Software Design](#software-design)

  - [CommSystem](#comm-system)

    - [Packet](#packet)
    - [CommHandler](#commhandler)
    - [SerialHandler](#serialhandler-previously-radiohandler)
    - [RockBlockHandler](#rockblockhandler)
    - [EmailHandler](#emailhandler)

  - [WebGUI](#webgui)

    - [WebGUI Flask](#webgui-flask)
    - [WebGUI Utils](#webgui-utils)

  - [Sensor Library](#sensor-library)

    - [CameraHandler](#camerahandler-usb-and-rpi-camera-support)
    - [gpsNavi](#gpsnavi-berrygps-imu)

  - [ME Integration](#me-integration)

    - [SleepyPi](#sleepypi)
    - [escController](#esccontroller)
    - [Navigation Script](#navigation-script)

  - [Testing](#testing)
  
# Overview

Repository for Virginia Tech ECE Major Design Experience Team "Triton" (Fall 2021- Spring 2022).

Contains software which provides a communication framework (Comm. System), WebGUI, power management, motor controls, etc. to allow a remote operator to control an autonomous ocean-wave-powered robot. The README contains high-level documentation, e.g. usage guide and APIs, as well as low-level implementation details.

## Installation

Our codebase operates using Python 3 on two Raspberry Pi 4s.

The environment on the provided robot and landbase Raspberry Pi's already have all needed dependencies installed. To install the dependencies on a fresh OS, we have provided a `requirements.txt` file for convenience.

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install the dependencies.

```bash
pip install requirements.txt
```

## Usage

### Accessing Raspberry Pi's via SSH

To access either the robot's or landbase's Raspberry Pi via SSH, it is recommended to use an ethernet cable, so they may be addressed via their host names, `pecanpi` and `pumpkinpi` respectively. To address a hostname over ethernet, simply set the remote host to `[hostname].local`, e.g. to SSH into the robot use `pecanpi.local`. IP addresses may also be used if they are known.

Any SSH software may be used. We recommend [*MobaXTerm*](https://mobaxterm.mobatek.net/), as it is what we used for our development.

### Running Primary Scripts

There are two primary python scripts within this repository `Triton_Robot.py` and `Triton_Landbase.py` to be run on the robot and landbase Raspberry Pi's respectively.

Either script can be started by simply running `python Triton_[Robot/Landbase].py` in the terminal.

By default, both the robot's and landbase's communication systems are set to `CommMode.HANDSHAKE`, i.e., they will wait until a connection is established before continuing (for more information see Software Design - Comm. System).

### Accessing the WebGUI

Once `Triton_Landbase.py` is running on the landbase's Pi, you may access the WebGUI. To do so, you may either use the landbase's hostname (pumpkinpi.local) if you are connecting over ethernet or you will need to find the Pi's IP address. To obtain this, SSH into the Pi via ethernet. Then, in the terminal, type `ip a`. Look for an IPv4 address under `wlan0`.

The WebGUI can be accessed on port 5000. As such, you will need to append `:5000` to the address in your browser, e.g. `pumpkinpi.local:5000` or `172.29.35.202:5000`.

### Using the WebGUI

After loading the WebGUI you will have access to all of the data from the robot. In order to send GPS coordinates for autonomous navingation you can either maually enter them in the input boxes or drop a pin on the Google Map. There is a button for requesting live control which will then open live video and a control panel with buttons that can be pressed to move the robot. All messages sent and recieved will appear in the log.
------

# Software Design

This section is intended to aid anyone who may use this repository in the future for further development. We will discuss higher level interfaces as well as low-level implementation details.

Our code can be separated into 5 main categories:

- <u>**Application Scripts**</u>: User-level scripts that are ran. Contains abstracted, high-level behavior of robot/landbase.
- **<u>WebGUI</u>**: Flask & Javascript framework to support the web graphical user interface.
- **<u>Comm. System</u>**: 'Layered' approach to providing reliable data transmission between robot and landbase.
- **<u>Sensor Library</u>**: Object-orientated paradigms of accessing sensor data on robot.
- **<u>Mechanical Engineering (ME) Integration</u>**: Contains implementation of motor controls and power management.

![](https://github.com/rlandry920/ComSys-for-Ocean-Power-Robots/blob/main/Resources/triton_software-dep-chart.png?raw=true)

------

## Comm System

### Packet

`Packet.py` describes the **<u>foundational data structure</u>** used by our communication system. Uses a datagram header to allow applications to interpret binary data contained w/i and ensure reliable data transfer.

This header contains a 4-byte `preamble` (also referred to as a "sync word") to provide a clear indication in a byte stream where a packet begins; a 1-byte `message type` label to allow interpretation of binary data; a 3-byte packet `ID` to uniquely identify a packet in RDT protocols, a 2-byte `checksum` to ensure data integrity; and a 2-byte `length` field to indicate how long the appended binary data is in bytes. Below is a diagram of this datagram header.

![](https://github.com/rlandry920/ComSys-for-Ocean-Power-Robots/blob/main/Resources/triton_packet-diagram.png?raw=true)

Packet.MsgType Enumerated Values

| Message Type                     | Hexadecimal Value | Description                                                  |
| -------------------------------- | ----------------- | ------------------------------------------------------------ |
| Null                             | 0x00              | Data w/i packet is meaningless and should be ignored         |
| Handshake                        | 0x01              | Used by comm. system to initialize a connection. Forwarded to high-level applications to notify a connection has been made. |
| Handshake Response               | 0x02              | Used by comm. system to confirm a connection. Forwarded to high-level applications to notify a connection has been made. Necessary to use a separate “response” type because handshake behavior is stateless. |
| Selective Acknowledgement (SACK) | 0x03              | Used by comm. system to acknowledge a packet has been received by other party during a RDT connection. |
| Duplicate Ack.(DACK)             | 0x04              | Used by comm. system to acknowledge a packet that has already been acknowledged. Interpreted the same as SACK by the recipient of the DACK. Useful for debugging purposes. |
| Cumulative Ack. (CACK)           | 0x05              | Used by comm. system to acknowledge all recently transmitted packets with and below the provided ID. *Currently not implemented.* |
| Text                             | 0x06              | General text data.                                           |
| Info                             | 0x07              | Non-critical application data.                               |
| Error                            | 0x08              | Relay critical application failures.                         |
| GPS Data                         | 0x09              | Data contains robot’s longitude, latitude, and compass information. |
| Image                            | 0x0A              | Data is a H264 encoded video frame for live video.           |
| Motor Command                    | 0x0B              | Data contains two float values ranging from -1 to 1 to directly power motors. Used for live control. |
| GPS Command                      | 0x0C              | Data contains GPS longitude and latitude, sent by the land base, to which the robot should autonomously navigate. |
| Motor Switch Command             | 0x0D              | Manually selects between the robot's heave-plate and wave-glider modes. *Unused.* |
| Control Request                  | 0x0E              | Indicates that landbase wishes to start/stop live control. Robot will begin/stop sending live video frames and processing motor commands. |
| UDP                              | 0x0F              | Data is from a 3rd party UDP packet to be forwarded to the other party. *For demonstration purposes currently*; *planned for AROV integration.* |
| Heartbeat Request                | 0x10              | Sent from land base periodically test comm. link with expectation that robot will respond with a heartbeat. Land base initiates this behavior (instead of robot autonomously sending heartbeats) to allow land base to monitor latency without time synchronization with robot. |
| Heartbeat                        | 0x11              | Response to heartbeat request. Contains status information like current state (idle, live control, autonomous navigation), GPS data, compass direction, and battery percentage. |
| Comm. Change                     | 0x12              | Forces the other party to change communication mode to the one specified in the data. *Unused*. |

#### API

Packet.Packet

| Function        | Description                                                  | Parameters                                                   |
| --------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| *__init\_\_*    | Parameterized Constructor. Two constructor modes: "direct" and "from binary".<br />Specifying `ptype` will directly set fields of packet to the specified parameters. Does ***not*** do any consistency checking, so it is recommended to only set `ptype` and `data`. <br />Specifying `data` and setting ptype to MsgType.NULL will perform the "from binary" constructor, attempting to set fields based on the binary data within `data` raises an exception if formatting of data does not match expectations. | `ptype`: Packet type, sets the message type and invokes "direct" constructor if not MsgType.NULL. default=MsgType.NULL<br />`pid`: Sets ID of the packet, will likely be overwritten by CommHandler if needed, so specifying it is seldom necessary. default=0<br />`data`: Binary string to contstruct packet from if using "from binary" constructor. If using "direct" constructor sets the *length* and *data* fields of the packet accordingly. default=b''<br />`calc_checksum`: Boolean indicating whether the checksum should be calculated and set at the end of packet construction. default=False<br />`cmode`: Lets CommHandler know over which communication link packet should be set. *Should* only be set to either None, CommMode.RADIO, or CommMode.SATELLITE. Specifying None will allow the CommHandler to decide where the packet goes. default=None |
| *to_binary*     | Returns the binary string of the packet object.              | None                                                         |
| *calc_checksum* | Mutes own checksum field, then returns calculated CRC-16 checksum of packet. | None                                                         |

### CommHandler

`CommHandler.py` contains the <u>**primary implementation of our communication system**</u>. It uses RDT protocols and multi-threading to handle sending and receiving data over multiple channels asynchronously. It also contains our handshake protocols to allow the robot and landbase to coordinate which channel to use.

#### API

CommHandler.CommHandler

| Function      | Description                                                  | Parameters                                                   |
| ------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| *__init\_\_*  | Constructor                                                  | `window_size`: Size of tx/rx windows (see selective-repeat ARQ). default = 8<br />`ordered_delivery`: Boolean whether or not to deliver received packets in order to the ingress queue. default = True<br />`handshake_timeout`: Time (in seconds) after starting in handshake mode without a connection that *CommMode.start()* should raise an exception. default = 1hr<br />`landbase`: Boolean  whether CommHandler is being used by landbase or not. Informs which satellite handler to use. default = True |
| *send_packet* | Appends a packet to the egress queue                         | `packet`: Packet to append to egress queue                   |
| *recv_packet* | Pops the topmost packet from the ingress queue. Returns `None` if queue is empty. | None                                                         |
| *recv_flag*   | Returns `True/False` whether there is a packet in the ingress queue. | None                                                         |
| *start*       | Begins the ingress and egress threads. Will begin in the specified CommMode. If `comm_mode` is set to `CommMode.HANDSHAKE`, will raise an exception after `handshake_timeout` seconds (see *__init\_\_*) if a connection has not yet been established. Also begins any relevant interface handlers (i.e. SerialHander, RockBlockHandler, EmailHandler) | `comm_mode`: Mode to start the Comm. System in. default = CommMode.HANDSHAKE |
| *reboot*      | Clears tx/rx windows and egress/ingress queues and changes mode to specified `comm_mode` | `comm_mode`: Mode to restart the Comm. System in. default = CommMode.HANDSHAKE |
| *stop*        | Closes and joins all ongoing threads relevant to CommHandler. | None                                                         |

#### Implementation Details

The current implementation of the CommHandler uses two threads, update_egress & update_ingress, to asynchronously send from / receive to the egress and ingress queues respectively. Whenever an application calls `CommHandler.send_packet()` or `CommHandler.recv_packet()`, it is only interacting with the egress & ingress queues.

Uses Selective Repeat ARQ standard to ensure reliable transmission of packets over an unreliable link, e.g. radio. Standard use 'windows' with which multiple in-flight packets may be sent to improve throughput. For more details on Selective Repeat ARQ, visit https://www.geeksforgeeks.org/sliding-window-protocol-set-3-selective-repeat/

<img src="https://media.geeksforgeeks.org/wp-content/uploads/Sliding-Window-Protocol.jpg" alt="Geek-for-Geeks Selective Repeat ARQ Example" style="zoom:50%;" />

### SerialHandler (previously RadioHandler)

`SerialHandler.py` is a class-based paradigm to send/receive data over a serial/UART channel. For our purposes, it is used to handle <u>**sending/receiving packets using the RFD900x**</u>.

Uses serial.threaded.protocol to implement asynchronous serial events. Specifically we use an asynchronous reader thread to read from the serial device and create packets when possible. See [pyersial.threaded readthedocs](https://pyserial.readthedocs.io/en/latest/pyserial_api.html#module-serial.threaded) more details on threaded implementation.

The below table describes pin connections between the Raspberry Pi (RPi) and RFD900x Radio Modem. For reference on RFD900x pins, visit: http://files.rfdesign.com.au/Files/documents/RFD900x%20DataSheet.pdf

| RaspberryPi => RFD900x Connection              | Description                                |
| ---------------------------------------------- | ------------------------------------------ |
| 5V => PIN3<br />GND => PIN1                    | Allows RPi to power RFD900x                |
| TX (GPIO 14) => PIN7<br />RX  (GPIO 15)=> PIN9 | UART Communication between RPi and RFD900x |

#### API

SerialHandler.SerialHandler

| Function       | Description                                                  | Parameters                      |
| -------------- | ------------------------------------------------------------ | ------------------------------- |
| *__init\_\_*   | Constructor                                                  | None                            |
| *start*        | Starts asynchronous reader thread.                           | None                            |
| *close*        | Stops asynchronous reader thread.                            | None                            |
| *write_packet* | Writes binary string of provided packet to the serial device. | `packet`: Packet object to send |
| *read_packet*  | Pops topmost read packet from received packets queue. Returns none if queue is empty. | None                            |

### RockBlockHandler

Coverts functions found in 3rd party API, rockBlock.py, into a format the matches our 'abstract' handler format, i.e. has callable write_packet and read_packet functions. Uses a threading to continously check the RockBLOCK for any new packets. See [MakerSnake rockBlock GitHub](https://github.com/MakerSnake/pyRockBlock) for more details on threaded implementation.

Assumes RockBLOCK is connected to the RaspberryPi via a USB to TTL cable operating on \dev\ttyUSB0.

#### API

| Function       | Description                                                  | Parameters                      |
| -------------- | ------------------------------------------------------------ | ------------------------------- |
| *__init\_\_*   | Constructor                                                  | None                            |
| *start*        | Starts asynchronous reader thread.                           | None                            |
| *close*        | Stops asynchronous reader thread.                            | None                            |
| *write_packet* | Writes binary string of provided packet to the serial device. | `packet`: Packet object to send |
| *read_packet*  | Pops topmost read packet from received packets queue. Returns none if queue is empty. | None                            |

### EmailHandler

Allows the landbase to communiate with satellite via email. Packets can be sent using write_packet and
an email will be created and sent using the gmail information that it is provided. Any messges sent from
the satellite will be delievered to the email registered with the satellite. The email will have an attatchment
that contains the body of the message. The read_packet function that will read any unread emails and if they are
from the iridium service, it will try to read the message and turn it in to a packet that is able to be read
by the CommSys

| Function       | Description                                                  | Parameters                      |
| -------------- | ------------------------------------------------------------ | ------------------------------- |
| *__init\_\_*   | Constructor                                                  | `username`: gmail connected to satellite<br />`password`: gmail login password                           |
| *start*        | Opens email for reading.                                     | None                            |
| *close*        | Logs out of email.                                           | None                            |
| *write_packet* | Sends email to iridium service with packet as an attatchment.| `packet`: Packet object to send |
| *read_packets*  | Reads all unread emails and tries to create packets from the attatchments. Returns an array of all new packets.|None                |

------

## WebGUI

This uses HTML, CSS, and JS. It is designed to show all of the data from the robot in a easily readable manner. It utilizes websockets to recieve data and live video feed and communicates with the Flask script using HTTP. 

### WebGUI Flask

This serves as a backend for the landbase in order to keep the UI seperate from all of the
commands. Each of the routes has a function attatched to it that will be run whenever the route
is accessed. The landbase can access these functions using HTTP. These function can then send messages
to the robot using the CommSys and also send messages back to the landbase using the websockets. This
also packs all of the HTML and JS together.

| Function          | Description                                                      | Parameters |
| ------------------| ---------------------------------------------------------------- | ---------- |
| *index*           | Returns HTML component                                           | None       |
| *script*          | Returns JS component                                             | None       |
| *reroute_js*      | Returns Decoder.js                                               | None       |
| *openWindow*      | Increments number of active users and broadcast new total number | None       |
| *closeWindow*     | Decrements number of active users and broadcast new total number | None       |
| *getNumUsers*     | Get total number of active users                                 | None       |
| *goToCoordinates* | Send new coordinates to the robot for autonomous navigations     | `lat_py`: Destination's latitude <br />`long_py`: Destination's longitude|
| *move*            | Send move command to robot at a specific speed                   | `command`: Direction of movement <br />`speed`: Speed of movement|
| *stop*            | Send stop command to robot                                       | None  |
| *reqLiveControl*  | Request live control of robot                                    | `enable`: Whether live control is being requested or stopped|

### WebGUI Utils

Contains utility functions that are used by the Flask script. These functions create packets that can
be sent to the robot using the CommSys.

| Function               | Description                                               | Parameters |
| ---------------------- | --------------------------------------------------------- | ---------- |
| *sendDirectionCommand* | Create motor command with values for left and right motor | `direction`: Direction of movement <br> `speed`: Speed of movement <br> `commHandler`: Used to allow Flask script to send packets directly to egress queue     |
| *sendMoveCommand*      | Create motor command with values for left and right motor | `latitude`: Destination's latitude <br />`longitude`: Destination's longitude|
| *getStringCoordinates* | Extracts latitude and longitude from dictionary           | `data`: dictionary that contains lat_py and long_py|       
| *checkCoordinates*     | Check to make sure latitude and longitude are both valid  | `latitude`: Destination's latitude <br />`longitude`: Destination's longitud
| *liveControl*          | Create live control request packet                        | `enable`: Whether live control is being reuqested or stopped       |

------

## Sensor Library

### CameraHandler (USB and RPi Camera Support)

Uses threading to take video frames and encode them for transmission. Supports either RaspberryPi Camera (for h264 encoding) or a USB Camera (for MJPEG encoding, depreciated - no longer supported by WebGUI).

| Function     | Description                                                  | Parameters                                                   |
| ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| *__init\_\_* | Constructor                                                  | `comm_handler`: Used to allow CameraHandler to send packets directly to egress queue without need application to manage encoded video frames.<br />`camera`: Accepts either a Picamera or USB camera to retrieve video frames from. Automatically selects between H264 and MJPEG encoding formats respectively. If None is passed, CameraHandler will use a default Picamera. |
| *start*      | Starts frame fetching and encoding thread. Video frames will automatically be placed into egress queue at start. | None                                                         |
| *Stop*       | Stops                                                        |                                                              |

### gpsNavi (BerryGPS-IMU)

Uses I2C interface to read NMEA sentence for interpreting GPS coordinates and calculate tilt compensated heading from IMUcompass. Supports RaspberryGPS-IMUv4 modem. 

| Function     | Description | Parameters |
| ------------ | ----------- | ---------- |
| *__init\_\_* | Constructor | `BerryGPS`: Used to detect BerryIMU and make connection, Automatically receive GPS signal and initialise the accelerometer, gyroscope and compass. <br />`IMU` : Used to allow detect the version of berryIMU in use and check I2C bus address, since the compass and accleerometer are oriented differently on the berryIMUv1, v2, v3, and v4.    |
| *readCompass*| Used to calculate tilt compensated heading values by applying compass calibration | None                                                         |
| *readGPS*    | Used to read data via I2C from IMU GPS module. Interpretes NMEA sentence data string to and turn out GPS coordinates like longitute and latitute, along with other informations like time stamp, date, and speed. | None                                                         |

------

## ME Integration

This category is used for a sundry of applications, but the primary two are navigation/locomotion and power management, handled within "Navigation Script"/"escController" and SleepyPi respectively.

### SleepyPi

The SleepyPi class defined in `SleepyPi.py` assumes that a SleepyPi running `LowVoltageShutdown_Triton.ino` is connected to the robot's Raspberry Pi using the pins below. Because the SleepyPi uses the same GPIO connector as the RaspberryPi the pins on both are the same

| RaspberryPi - SleepyPi Connection | Description                                                  |
| --------------------------------- | ------------------------------------------------------------ |
| 5V & Ground                       | Allows SleepyPi to power RPi w/ 12-30V battery.              |
| I2C SDA (GPIO 2) and SCL (GPIO 3) | Allows SleepyPi to advertise voltages to RPi.                |
| GPIO 24                           | SleepyPi will raise this pin high to notify the RPi that it should safely shutdown. Leaving this pin floating may cause the RPi to fail to boot! |
| GPIO 25                           | RPi will drive this pin high to notify the SleepyPi that it is running. |

#### API

SleepyPi.SleepyPi

| Function         | Description                                                  | Parameters                                                   |
| ---------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| *__init\_\_*     | Constructor. Drives GPIO 25 high to notify SleepyPi that script is running. | `shutdown_target`: Callable function that will be executed if a shutdown signal is received during *check_shutdown()*. |
| *read_voltage*   | Uses I2C bus to obtain most recent battery voltage reading from SleepyPi. Returns the float value from the SleepyPi or None if I2C communication failed. | None                                                         |
| *check_shutdown* | Returns whether GPIO 24 was driven high. Calls `shutdown_target` if specified in constructor. | None                                                         |

#### LowVoltageShutdown_Triton.ino

Altered version of the `LowVoltageShutdown.ino` example in the SleepyPi Arduino library.

Sends shutdown signal to Raspberry Pi if battery voltage drops below 24.12 V. For two car batteries (whose full charge is expected to be 25.2 V), 24.12V is ~20% battery. Once the RPi is off, i.e. no longer driving GPIO 25, the SleepyPi cuts power. If measured voltage drops below 23.5 V, power is cut immediately.

Uses debouncing to ensure noise doesn't cause sudden shutdowns.

Refer to [this guide](https://spellfoundry.com/docs/programming-the-sleepy-pi-as-a-standalone-board/) for details on programming the SleepyPi.

### escController

Used to establish the motor connection as well as handle all motor functionalities. This script should be able to interpret user input data to turn a specified motor in any direction. 

| Function     | Description | Parameters |
| ------------ | ----------- | ---------- |
| *arm* | The arm function is called to “kickstart” these motors and will always have to be called first to start controlling the motors. One thing to note is that in order to arm ESC motors they need to be set to the minimum, maximum and stoppage values to start being able to manually control them. As you notice delays are set in between each one to prevent data overflow. | None |
| *setSpeed* | The setSpeed function does as it says and changes the speed given a motor and a newSpeed parameter. The main function we use here is pi.set_servo_pulsewidth() that sets the new PWM frequency of a motor. The function starts with setting a local curr speed variable to the motor's current speed. This allows us to use one variable to reference our current speed of whichever motor was passed through. After that is done, a check is put in place to see if our motors are traveling from forwards to backwards or backwards to forwards. If it was then we would reset our motor speed to stop first then go to the new speed. We noticed that if we didn't have this check the motor would not be able to handle the large jump in speed and stop the program. With this check, if it changes directions it will go to the stop value, 1500, first then go to the new speed specified. Another if statement is then used to check to see if the new speed passed through were in between -.15 and .15. During testing, we noticed these numbers were causing the motors to stop the program so if a speed specified were in these ranges we would reset it to be at the stop value. Lastly we set our current value global variable to be the new speed. | `pickMotor`: Pinout value for one of the motors `setSpeed`: Speed value expected to be -1 to 1 | 
| *stop* | Stop is used to be able to make a quick call to turn off the motors. Both motors are set to 0 using pi.set_servo_pulsewidth() then pi.stop() is used to end the current pi connection. | None |


### Navigation Script

Contains functions that take can calculate the best path based to a destination based on
current coordinates.

| Function            | Description                                                       | Parameters |
| --------------------| ----------------------------------------------------------------- | ---------- |
| *find_bearing*      | Calculates bearing between 2 points                               | `lat1`: Latitude of first point `long1`: Longitude of first point `lat2`: Latitude of second point `long2`: Longitude of second point       |
| *find_turn_dir*     | Calculates which direction to turn to get to face the correct way | `curr_dir`: Current direction the robot is facing `bearing`: Direction that the robot should be facing         |
| *find_distance*     | Calculates the distance between 2 points                          |`lat1`: Latitude of first point `long1`: Longitude of first point `lat2`: Latitude of second point `long2`: Longitude of second point       |
| *find_path_to_coor* | Calculates path between 2 points                                  | `lat1`: Latitude of first point `long1`: Longitude of first point `lat2`: Latitude of second point `long2`: Longitude of second point       |

------

## Testing

### CommTestbench

We created a testing script `CommTestbench.py` to evaluate the performance of our communication system over radio. It implements three tests: latency, packet loss, and throughput. The script either accepts arguments or user input when ran with `python CommTestbench.py`

Script with same parameters (except for sender/receiver) must be ran on both Raspberry Pis.

<u>Arguments:</u>

- `-d` or `--debug` Enables debug output
- `-t` or `--throughput` Selects throughput test
- `-p` or `--packetloss` Selects packet loss test
- `-l` or `--latency` Selects latency test
- `-s` or `--sender` Runs test as the sender
- `-r` or `--receiver` Runs test as receiver
- `-n [value]` or `--number [value]` Sets number of packets to be sent during test to *value*
- `--size` Set size (in bytes) of each packet sent during test to *value*

<u>Example usage:</u>

On sender:

```python CommTestbench.py --throughput -s -n 20 --size 256 ```

On receiver:

```python CommTestbench.py --throughput -r -n 20 --size 256```
