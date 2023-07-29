from dronekit import Vehicle, LocationGlobal, LocationGlobalRelative, VehicleMode, Command
from pymavlink import mavutil
from optics import Eye, PadType, intoPadType
from compute import *
from poltergeist import Result, Ok, Err, catch
from typing import List, Tuple
from datetime import datetime
from constants import *
import logging
import time

# TODO: Remove the | None

class Resolve:
    """
    Represents the wanted state of the vehicle, is computed on a 
    tick of the state machine.
    """

    yaw: int | None
    position: LocationGlobal | None
    velocity: Tuple[float, float, float] | None
    transitionAvailable: bool
    padType: PadType | None

    def __init__(
            self, 
            yaw: int | None, 
            position: LocationGlobal | None, 
            transitionAvailable: bool, 
            velocity: Tuple[float, float, float] | None = None,
            padType: PadType | None = None):
        self.yaw = yaw
        self.position = position
        self.transitionAvailable = transitionAvailable
        self.velocity = velocity
        self.padType = padType

class Idle:
    name = "Idle"
    sinceStatusUpdate: datetime
    vehicle: Vehicle

    def __init__(self, vehicle: Vehicle) -> None:
        self.sinceStatusUpdate = datetime.now()
        self.vehicle = vehicle

    @catch(Exception)
    def tick(self) -> Resolve:
        # Transition out of idle if 
        # - in the air and
        # - armed and
        # - in the AUTO flight mode and
        # - actively in a GUIDED_ENABLE waypoint
        inAir = (self.vehicle.location.global_relative_frame.alt is not None) and self.vehicle.location.global_relative_frame.alt >= MIN_ALT_FOR_FLIGHT
        armed = self.vehicle.armed
        auto = self.vehicle.mode == VehicleMode("AUTO")

        if self.vehicle.commands.next == 0:
            currWayId: int = self.vehicle.commands[self.vehicle.commands.next].command # type: ignore
            param: int = self.vehicle.commands[self.vehicle.commands.next].z
        else:
            # When a GUIDED_ENABLE waypoint is reached, the `next` is silently
            # updated to the next waypoint after GUIDED_ENABLE. To see if we
            # are currently guided enable, see the last waypoint command.
            currWayId: int = self.vehicle.commands[self.vehicle.commands.next - 1].command # type: ignore
            param: int = self.vehicle.commands[self.vehicle.commands.next - 1].z

        
        validParam = intoPadType(param) is not None
        guided = currWayId == 92 # 92 = GUIDED_ENABLE

        # Status update
        if (datetime.now() - self.sinceStatusUpdate).seconds >= STATUS_UPDATE_FREQ:
            logging.info("Vehicle is idling.")
            logging.info("inAir: %s, armed: %s, auto: %s, alt: %s, command: %s", 
                         inAir, 
                         armed, 
                         auto, 
                         self.vehicle.location.global_relative_frame.alt,
                         currWayId
                         )
            self.sinceStatusUpdate = datetime.now()

        if inAir and armed and auto and guided and validParam:
            return Resolve(None, None, True, padType=intoPadType(param))
        return Resolve(None, None, False)

class Descent:
    name = "Descending"
    vehicle: Vehicle
    eye: Eye
    conductor: Conductor
    padType: PadType | None

    sinceStatusUpdate: datetime
    sinceEnter: datetime
    commandId: int

    def __init__(self, vehicle: Vehicle, eye: Eye, conductor: Conductor, padType: PadType | None):
        self.vehicle = vehicle
        self.eye = eye
        self.conductor = conductor
        self.sinceStatusUpdate = datetime.now()
        self.sinceEnter = datetime.now()
        self.commandId = vehicle.commands.next
        self.padType = padType

    @catch(Exception)
    def tick(self) -> Resolve:
        altGuess = getAGL(self.vehicle)
        locationDetects: List[LocationDetection] = []
        pixelDetects = self.eye.tick().unwrap()
        if pixelDetects is not None:
            for d in pixelDetects:
                dist = relativeDistance(
                    altGuess, # type: ignore
                    d.normalizedCoords,
                    self.vehicle.attitude.yaw # type: ignore
                )
                loc = distanceToLocation(self.vehicle.location.global_frame, dist)

                locationDetects.append(LocationDetection(d.padType, loc, d.confidence))
        self.conductor.add_detections(locationDetects)

        if self.padType is None:
            bestGuess = self.conductor.get_best_guess(PadType.bottlePickup)
        else:
            bestGuess = self.conductor.get_best_guess(self.padType)

        # Status update
        # Uncomment this after testing
        if (datetime.now() - self.sinceStatusUpdate).seconds >= STATUS_UPDATE_FREQ:
            logging.info("Vehicle is descending! cacheSize: %s, guess: %s, airspeed: %s, id: %s",
                            len(self.conductor.detections),
                            bestGuess,
                            self.vehicle.airspeed,
                            self.vehicle.commands.next
                            )
            self.sinceStatusUpdate = datetime.now()

        if altGuess <= ALIGN_ALT:
            # We can align
            return Resolve(None, None, True)

        if bestGuess is not None:
            dists = individualDist(bestGuess.location, self.vehicle.location.global_frame)
            angle = angleDiff(dists, altGuess)

            if angle[0] <= MAX_ANGLE_DIFF and angle[1] <= MAX_ANGLE_DIFF:
                downOffset = LocationGlobal(
                    bestGuess.location.lat, 
                    bestGuess.location.lon,
                    self.vehicle.location.global_frame.alt - DESCENT_SPEED
                )
                return Resolve(0, downOffset, False)

            return Resolve(0, bestGuess.location, False)
        # Become optimistic if haven't found the proper pad type
        elif (datetime.now() - self.sinceEnter).seconds >= OPTIMISM_TIME and not self.conductor.optimistic:
            self.conductor.optimistic = True
            logging.warn("Conductor became optimistic!")

        return Resolve(None, None, False)
    
class Align:
    name = "Aligning"
    vehicle: Vehicle
    eye: Eye
    conductor: Conductor

    sinceEnter: datetime
    commandId: int

    def __init__(self, vehicle: Vehicle, eye: Eye, conductor: Conductor, commandId: int) -> None:
        self.vehicle = vehicle
        self.eye = eye
        self.conductor = conductor
        self.sinceEnter = datetime.now()
        self.commandId = commandId

    @catch(Exception)
    def tick(self) -> Resolve:
        if (datetime.now() - self.sinceEnter).seconds >= ALIGN_TIME:
            return Resolve(None, None, True)

        altGuess = getAGL(self.vehicle)
        locationDetects: List[LocationDetection] = []
        pixelDetects = self.eye.tick().unwrap()
        if pixelDetects is not None:
            for d in pixelDetects:
                dist = relativeDistance(
                    altGuess, # type: ignore
                    d.normalizedCoords,
                    self.vehicle.attitude.yaw # type: ignore
                )
                converted = changeMagnitude(dist, ALIGN_AIRSPEED)
                return Resolve(None, None, False, (converted[0], converted[1], 0.0))

                # loc = distanceToLocation(self.vehicle.location.global_frame, dist)

                # locationDetects.append(LocationDetection(d.padType, loc, d.confidence))
        # self.conductor.add_detections(locationDetects)

        """

        bestGuess = self.conductor.get_best_guess(PadType.bottlePickup)
        if bestGuess is not None:
            pos = LocationGlobalRelative(bestGuess.location.lat, bestGuess.location.lon, ALIGN_ALT)
            return Resolve(None, pos, False)

        """

        return Resolve(None, None, False, (0.0, 0.0, 0.0))
    
class Touchdown:
    name = "Touching down"
    vehicle: Vehicle
    eye: Eye

    commandId: int

    def __init__(self, vehicle, eye, commandId) -> None:
        self.vehicle = vehicle
        self.eye = eye
        self.commandId = commandId
    
    @catch(Exception)
    def tick(self) -> Resolve:
        altGuess = getAGL(self.vehicle)

        if altGuess <= LANDED_ALT_LIDAR:
            return Resolve(None, None, True)

        locationDetects: List[LocationDetection] = []
        pixelDetects = self.eye.tick().unwrap()
        if pixelDetects is not None:
            for d in pixelDetects:
                if d.padType == PadType.padCenter:
                    dist = relativeDistance(
                        altGuess, # type: ignore
                        d.normalizedCoords,
                        self.vehicle.attitude.yaw # type: ignore
                    )
                    converted = changeMagnitude(dist, AIRSPEED)

                    return Resolve(None, None, False, (converted[0], converted[1], TOUCHDOWN_SPEED))

        return Resolve(None, None, False, (0, 0, TOUCHDOWN_SPEED))


class Landing:
    state: Idle | Descent | Align | Touchdown
    vehicle: Vehicle
    eye: Eye
    padType: PadType | None
    
    def __init__(self, eye: Eye, vehicle: Vehicle) -> None:
        self.eye = eye
        self.vehicle = vehicle
        self.state = Idle(vehicle)
        padType = None

    def idle(self) -> None:
        """
        Enter the idle stage immediately.
        """
        self.state = Idle(self.vehicle)

    def transition(self) -> None:
        """
        Transition into the next stage:
        Idle -> Descent -> Align -> ...
        """
        if isinstance(self.state, Idle):
            logging.info("Transition into Descent...")

            logging.info("Tracking a %s", self.padType.value)
            self.state = Descent(self.vehicle, self.eye, Conductor(), self.padType)
        elif isinstance(self.state, Descent):
            logging.info("Transition into Align. Alt: %s", getAGL(self.vehicle))
            self.state = Align(self.vehicle, self.eye, self.state.conductor, self.state.commandId)
        elif isinstance(self.state, Align):
            logging.info("Transition into Touchdown...")
            self.state = Touchdown(self.vehicle, self.eye, self.state.commandId)
        elif isinstance(self.state, Touchdown):
            logging.info("Touchdown finished!")

            # Make the vehicle descend straight down the final strech
            self.vehicle.mode = VehicleMode("LAND")
            # Wait until we have disarmed 
            while self.vehicle.armed == True:
                time.sleep(0.1) # 10hz check

            logging.info("Vehicle disarmed!")

            # Land mode isn't armable
            self.vehicle.mode = VehicleMode("LOITER")

            # Vehicle needs to be armed to proceed with mission
            while not self.vehicle.is_armable:
                logging.info("Waiting for vehicle to become armable...")
                time.sleep(0.5)
            # This sleep is necessary 
            time.sleep(1.5)

            self.vehicle.arm(wait=True)

            self.vehicle.mode = VehicleMode("AUTO")

            msg = self.vehicle.message_factory.command_long_encode(
                0, 0,    # target system, target component
                mavutil.mavlink.MAV_CMD_MISSION_START,  #command
                0, 
                0,   
                0,          
                0,          
                0, 
                0, 0, 0)    
            # Send command to vehicle
            self.vehicle.send_mavlink(msg)

            self.vehicle.commands.next = self.state.commandId + 1
            
            logging.info("Transition back into Idle...")
            self.state = Idle(self.vehicle)


    def tick(self) -> Result[Resolve, Exception]:
        # Special generic bs, this is allowed 
        return self.state.tick() # type: ignore