from pathlib import Path

# Dictates stuff like whether we should connect to sitl or UART,
# should we print to stdout or the drone GCS console.
DEVELOPMENT_MODE = True

LOGS_DIRECTORY = Path("/home/pi/flight_logs/")

TPS = 15 # How many ticks per second

MAX_FAILURES = 30

PAD_BLOBBING_DIST = 8 # meters

# This should be smaller than WPNAV_SPEED_DN
DESCENT_SPEED = 1.0 # m/s

TOUCHDOWN_SPEED = 0.3 # m/s

ALIGN_AIRSPEED = 0.3 # m/s

AIRSPEED = 0.8 # m/s

# The minimum altitude to consider the AV is flying, relative
# to the altidude of the home location.
MIN_ALT_FOR_FLIGHT = 5

STATUS_UPDATE_FREQ = 1 # In seconds

# How long the alignment phase will go for
ALIGN_TIME = 25 # In seconds

ALIGN_ALT = 3 # in meters

# How long until the Conductor becomes optimistic about pad
# types.
OPTIMISM_TIME = 999 # In seconds

# The maximum angle of error between a pad and the drone
# that the drone will still descend in.
MAX_ANGLE_DIFF = 25 # In degrees

# The distance the rangefinder will read when the drone
# is landed ( + upward tolerance).
LANDED_ALT_LIDAR = 0.5 # In meters