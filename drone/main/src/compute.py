from math import tan, radians, sqrt, atan2, pi, sin, cos, degrees
from typing import Tuple, List
from optics import PixelCoords, HEIGHT_FOV, WIDTH_FOV, PixelDetection, PadType
from constants import PAD_BLOBBING_DIST
from dronekit import LocationGlobal, Vehicle

def dist(aLocation1: LocationGlobal, aLocation2: LocationGlobal) -> float:
    """
    Returns the ground distance in metres between two `LocationGlobal` objects.

    This method is an approximation, and will not be accurate over large distances and close to the
    earth's poles. It comes from the ArduPilot test code.
    """
    dlat = aLocation2.lat - aLocation1.lat
    dlong = aLocation2.lon - aLocation1.lon
    return sqrt((dlat*dlat) + (dlong*dlong)) * 1.113195e5

def individualDist(loc1: LocationGlobal, loc2: LocationGlobal) -> Tuple[float, float]:
    dlat1 = LocationGlobal(loc1.lat, 0.0, 0.0) 
    dlat2 = LocationGlobal(loc2.lat, 0.0, 0.0) 

    dlon1 = LocationGlobal(0.0, loc1.lon, 0.0) 
    dlon2 = LocationGlobal(0.0, loc2.lon, 0.0)

    return (dist(dlat1, dlat2), dist(dlon1, dlon2)) 

class LocationDetection:
    padType: PadType
    location: LocationGlobal
    confidence: float

    def __init__(self, padType, location, confidence) -> None:
        self.padType = padType
        self.location = location
        self.confidence = confidence

    def __str__(self) -> str:
        return "{" + str(self.confidence) + "; lat " + str(self.location.lat) + "; lon " + str(self.location.lon) + "}"

class Conductor:
    detections: List[LocationDetection]
    optimistic: bool

    def __init__(self):
        self.detections = []
        self.optimistic = False

    def add_detections(self, new: List[LocationDetection]) -> None:
        """
        Adds a list of detections to this conductor, and blobs some
        if they are too similar.
        """

        for detNew in new:
            blobbed = False
            for det in self.detections:
                if detNew.padType == det.padType and dist(detNew.location, det.location) <= PAD_BLOBBING_DIST:
                    # Average out the positions
                    det.location.lat += detNew.location.lat
                    det.location.lat /= 2
                    det.location.lon += detNew.location.lon
                    det.location.lon /= 2

                    # Add to the confidence
                    det.confidence += detNew.confidence
                    blobbed = True
                    break
            if not blobbed:
                self.detections.append(detNew)

    def get_best_guess(self, type: PadType) -> LocationDetection | None:
        """
        Gets the best guess for a pad location, based on a pad type
        """

        best: LocationDetection | None = None

        for det in self.detections:
            if (self.optimistic or det.padType == type) and (best is None or det.confidence > best.confidence):
                best = det

        return best


def relativeDistance(altitude: int, coords: PixelCoords, yaw: int) -> Tuple[float, float]:
    """
    Given the vehicle altitude, and some normalized pixel coords (0.0 - 1.0),
    output the relative horizontal distance from the AV, to the coords. Essentially,
    convert from viewport to relative world position.

    This calculation does consider the AV's yaw (in degrees), but not orientation in 
    general.
    """
    viewportWidth = 2.0 * ( tan(radians(WIDTH_FOV / 2.0)) * altitude )
    viewportHeight = 2.0 * ( tan(radians(HEIGHT_FOV / 2.0)) * altitude )
    coordsShifted = (coords.x - 0.5, (1.0 - coords.y) - 0.5)
    vector = (coordsShifted[0] * viewportWidth, coordsShifted[1] * viewportHeight)

    # The vector needs to be compensated for yaw
    magnitude = sqrt((vector[0] * vector[0]) + (vector[1] * vector[1]))
    angleRad = atan2(vector[1], vector[0])
    angleRad += radians(yaw)
    return (magnitude * cos(angleRad), magnitude * sin(angleRad))

def angleDiff(
    distances: Tuple[float, float], altDiff: float
) -> Tuple[float, float]:
    """
    Returns the difference in degrees between two objects if they are
    `distances` apart and `altDiff` apart.
    """

    x = degrees(atan2(distances[0], altDiff))
    y = degrees(atan2(distances[1], altDiff))

    return (y, x) # im not sure why flip these


def distanceToLocation(original_location: LocationGlobal, distance: Tuple[float, float]) -> LocationGlobal:
    """
    Returns a LocationGlobal object containing the latitude/longitude metres from the
    specified `original_location`. The returned LocationGlobal has the same `alt` value
    as `original_location`.

    The function is useful when you want to move the vehicle around specifying locations relative to
    the current vehicle position.

    The algorithm is relatively accurate over small distances (10m within 1km) except close to the poles.

    For more information see:
    http://gis.stackexchange.com/questions/2951/algorithm-for-offsetting-a-latitude-longitude-by-some-amount-of-meters
    """
    dNorth = distance[1]
    dEast = distance[0]
    earth_radius=6378137.0 #Radius of "spherical" earth
    #Coordinate offsets in radians
    dLat = dNorth/earth_radius
    dLon = dEast/(earth_radius*cos(pi*original_location.lat/180))

    #New position in decimal degrees
    newlat = original_location.lat + (dLat * 180/pi)
    newlon = original_location.lon + (dLon * 180/pi)
    
    targetlocation=LocationGlobal(newlat, newlon,original_location.alt)

    return targetlocation

def changeMagnitude(vector: Tuple[float, float], mag: float) -> Tuple[float, float]:
    if vector == (0, 0):
        return (0, 0)
    angle = atan2(vector[1], vector[0])
    return (mag * cos(angle), mag * sin(angle))

def getAGL(vehicle: Vehicle) -> float:
    """
    Attempts to get a AGL altitude (rangefinders)
    """
    if (vehicle.rangefinder is not None 
        and vehicle.rangefinder.distance is not None
        and vehicle.rangefinder.distance != 0.0
        and vehicle.location.global_relative_frame.alt <= 2.0):
        return vehicle.rangefinder.distance
    return vehicle.location.global_relative_frame.alt