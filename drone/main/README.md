# Venus Guidance System

This is the actual guidance system.

## The Goal

This system should guide a connected quadcopter onto a point of interest (detected by the image recognition models), and land on it. The guidance should be well-tested, have proper failsafes, and be precise. The system should integrate well into ArduPilot **AUTO** missions, so you can string together the guidance from this system and ArduPilot's prebuilt commands.

## The Implementation

This guidance system should run on an on-board raspberry pi which is connected to the main flight controller. When the AV is armed, flying, in **AUTO** and currently in a **GUIDED_ENABLE** command, the guidance system initiates, and guides the vehicle to precisely land on a POI. 
* The type of POI is provided to the guidance system as a numerical id on the Altitude field of the **GUIDED_ENABLE** command. 
* If the guidance system fails, the vehicle enters **RTL** mode. 
* When the landing is successful, the next command in the mission is executed. **GUIDED_ENABLE should not be last command in the mission.**