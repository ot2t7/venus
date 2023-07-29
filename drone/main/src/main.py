from dronekit import connect, Vehicle, VehicleMode, LocationGlobal
from poltergeist import Ok, Err
from pymavlink import mavutil
from pathlib import Path
from typing import Any
from datetime import datetime
import time
import logging
import os

from optics import Eye
from constants import *
from compute import relativeDistance
from landing import Landing, Idle

# Set up logging
logFile = None
videoTapeFile = None
if not DEVELOPMENT_MODE:
    if not LOGS_DIRECTORY.exists():
        os.mkdir(LOGS_DIRECTORY)

    logId = 0
    for _ in LOGS_DIRECTORY.iterdir():
        logId += 1
    logDir = LOGS_DIRECTORY.joinpath(str(logId))
    os.mkdir(logDir)
    logFile = logDir.joinpath("venus.log")

    videoTapeFile = logDir.joinpath("camera.h265")
logging.basicConfig(
    level=logging.INFO, 
    filename=logFile, 
    format='( %(asctime)s ) %(message)s', 
    datefmt='%m/%d/%Y %I:%M:%S %p'
)

def condition_yaw(vehicle: Vehicle, heading: int, relative=False) -> None:
    if relative:
        is_relative=1 #yaw relative to direction of travel
    else:
        is_relative=0 #yaw is an absolute angle
    # create the CONDITION_YAW command using command_long_encode()
    msg = vehicle.message_factory.command_long_encode(
        0, 0,    # target system, target component
        mavutil.mavlink.MAV_CMD_CONDITION_YAW, #command
        0, #confirmation
        heading,    # param 1, yaw in degrees
        0,          # param 2, yaw speed deg/s
        1,          # param 3, direction -1 ccw, 1 cw
        is_relative, # param 4, relative offset 1, absolute angle 0
        0, 0, 0)    # param 5 ~ 7 not used
    # send command to vehicle
    vehicle.send_mavlink(msg)

def send_ned_velocity(velocity_x: float, velocity_y: float, velocity_z: float) -> None:
    """
    Move vehicle in direction based on specified velocity vectors.
    A POSITIVE Z VALUE IS DOWN!
    """
    msg = vehicle.message_factory.set_position_target_local_ned_encode(
        0,       # time_boot_ms (not used)
        0, 0,    # target system, target component
        mavutil.mavlink.MAV_FRAME_LOCAL_NED, # frame
        0b0000111111000111, # type_mask (only speeds enabled)
        0, 0, 0, # x, y, z positions (not used)
        velocity_x, velocity_y, velocity_z, # x, y, z velocity in m/s
        0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
        0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)
    
    vehicle.send_mavlink(msg)

# This doesn't throw an exception, but pauses forever when
# connection cannot be made.
if DEVELOPMENT_MODE == True:
    connectionString = "127.0.0.1:14550"
    vehicle = connect(connectionString, wait_ready=True)
else:
    connectionString = "/dev/ttyAMA1"
    vehicle = connect(connectionString, wait_ready=True, baud=115200)

# Attempt to create an Eye
match Eye.new(videoTapeFile):
    case Ok(e):
        logging.info("Initialized an eye.")
        eye = e
    case Err(e):
        logging.info("Unable to initialize optics due to error: " + str(e.args))
        logging.info("Venus will now exit due to a critical error. Power cycle the AV.")
        exit(1)

# Landing sequence
machine = Landing(eye, vehicle)

# Download the current mission
vehicle.commands.download()
vehicle.commands.wait_ready()
timeSinceDownload = datetime.now()

# Notify we have connected!
vehicle.mode = VehicleMode("LOITER")

# How many times we have had an error
failures = 0

while True:
    time.sleep(1.0 / TPS)

    if failures >= MAX_FAILURES:
        vehicle.mode = VehicleMode("RTL")
        logging.info("We have reached the maximum failures!")
        logging.info("Venus will now exit due to a critical error. Power cycle the AV.")
        time.sleep(1.0)
        exit(1)

    if (datetime.now() - timeSinceDownload).seconds >= 5.0 and isinstance(machine.state, Idle):
        # Download the current mission
        logging.info("Downloading mission...")
        vehicle.commands.download()
        try:
            vehicle.commands.wait_ready(timeout=5)
        except:
            logging.error("Failed downloading mission.")
        timeSinceDownload = datetime.now()

    # The machine needs needs to be idled if
    # - it's disarmed or
    # - it's flight mode isn't AUTO or GUIDED
    if not vehicle.armed or (vehicle.mode != VehicleMode("AUTO") and vehicle.mode != VehicleMode("GUIDED")):
        # Don't needlessy transition into idle
        if not isinstance(machine.state, Idle):
            logging.info("Current mode: " + vehicle.mode.name)
            logging.info("Killing! Going back into Idle.")
            machine.idle()

    match machine.tick():
        case Ok(resolve):
            resolve = resolve
            if resolve.padType is not None:
                machine.padType = resolve.padType

            if resolve.transitionAvailable:
                machine.transition()

            # Do the resolved moments here, and nowhere else
            # TODO: Fix yaw issues
            if resolve.position is not None:
                vehicle.simple_goto(resolve.position, airspeed=AIRSPEED)
            #if resolve.yaw is not None:
                #condition_yaw(vehicle, resolve.yaw, False)
            if resolve.velocity is not None:
                v = resolve.velocity
                send_ned_velocity(v[0], v[1], v[2])
        case Err(e):
            logging.info("An error occured while in " + machine.state.name + " stage: " + str(e.args)) 
            failures += 1

    match eye.updateVideoTape():
        case Err(e):
            logging.info("Saving video file failed this tick: " + str(e.args))
            failures += 1
            # We can semi-safely ignore this error