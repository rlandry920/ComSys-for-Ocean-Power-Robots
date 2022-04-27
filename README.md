# Communication System for Ocean Power Robots

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

@Ryan TODO, but keep it brief

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

## Comm. System

### Packet

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



### SerialHandler (previously RadioHandler)

`SerialHandler.py` is a class-based paradigm to send/receive data over a serial/UART channel. For our purposes, it is used to handle <u>**sending/receiving packets using the RFD900x**</u>.

### RockBlockHandler

### Email Handler



## WebGUI



## Sensor Library

### CameraHandler (USB and RPi Camera Support)

### gpsNavi (BerryGPS-IMU)

@Qianhui TODO

## ME Integration

### SleepyPi

### escController

### Navigation Script

@Ryan/@Kurby TODO

## Testing

