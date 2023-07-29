# How to calibrate our drone!
Let's say you got your hands on the exact drone built on this project, but it hasn't been calibrated at all, and now you need to calibrate it's instruments. The following is a list of calibrations you will have to do:

- Calibrate Accelerometers in SETUP by turning it to each individual side and clicking done on the prompt. 
- Calibrate the compass using the "Relaxed" fitness setting. Turn it on each individual axis about 4 different times or until the bar fills up 4 - 8 times and it finishes. There is a compass on the GPS unit, and theres a gyroscope on the flight controller. ArduCopter combines both of these instruments to generate accurate headings. 
- The Compass doesn't really need calibration but it needs to be in an outdoor enviornment that is not cellularly blocked in anyway. 
- The barometer needs to be calibrated but the only thing that needs to be calibrated is the ground altitude the change in meters up or down is accurate out of the box, at least for us. 
- UART3 maps to SERIAL4 on ArduPilot, so we set SERIAL4_PROTOCOL setting to MSP. The SERIAL4_BAUD is set to 115k. The RNGFND4_TYPE and FLOW_TYPE is set to MSP.
- Follow this guide up until the "Other parameters" in order to setup the RFD transmitters on the ground station and the AV. https://ardupilot.org/copter/docs/common-configuring-a-telemetry-radio-using-mission-planner.html#common-configuring-a-telemetry-radio-using-mission-planner
- Calibrate the radio, so the transmitter unit on the ground sends correct signals.
- PID Tuning
- Setup servo gimbal for camera, pitch only. RC8 is Mount Lock, and RC6 is the actual pitch control.

- Change the crash angle, since currently it would just wall out of the sky with any wind
- Current fail safes (no fc signal) causes the drone to cut power and die
- Fix all the flight modes
- Setup battery monitoring and other failsafes