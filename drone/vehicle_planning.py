# If you get errors: just comment out the exception. not even kidding.

from dronekit import connect
from pathlib import Path
from time import sleep

def status_printer(txt):
    # Do nothing
    return

print("Waiting for connection...")
vehicle = connect("127.0.0.1:14550", wait_ready=True, status_printer=status_printer)

bottle_pickup = None
bottle_dropoff = None
medkit_pickup = None
medkit_dropoff = None
smores_pickup = None
smores_dropoff = None

chunk = Path("../missions/poi_chunk.waypoints").read_text()

def output_loc():
    pos = vehicle.location.global_frame
    print("Gotcha. Current location: (" + str(pos.lat) + ", " + str(pos.lon) + ")")

def exists(inp, text):
    return inp.find(text) != -1

while True:
    command = input("Input: ")
    command = command.lower()

    if exists(command, "exit") or exists(command, "stop"):
        print("Finishing.")
        break
    elif (exists(command, "bottle") or exists(command, "water")) and exists(command, "pick"):
        bottle_pickup = vehicle.location.global_frame
        output_loc()
    elif (exists(command, "bottle") or exists(command, "water")) and exists(command, "drop"):
        bottle_dropoff = vehicle.location.global_frame  
        output_loc()
    elif exists(command, "med") and exists(command, "pick"):
        medkit_pickup = vehicle.location.global_frame
        output_loc()
    elif exists(command, "med") and exists(command, "drop"):
        medkit_dropoff = vehicle.location.global_frame
        output_loc()
    elif exists(command, "smore") and exists(command, "pick"):
        smores_pickup = vehicle.location.global_frame
        output_loc()
    elif exists(command, "smore") and exists(command, "drop"):
        smores_dropoff = vehicle.location.global_frame
        output_loc()
    else:
        print("I'm not sure what that means.")

output_mission = ""
curr_idx = 1 # has to be 1

if medkit_pickup is not None and medkit_dropoff is not None:
    print("Embedding medkit stuff...")
    curr_chunk = (chunk + '.')[:-1] # Clones the string
    curr_chunk = curr_chunk.replace("LATITUDE1", str(medkit_pickup.lat))
    curr_chunk = curr_chunk.replace("LONGITUDE1", str(medkit_pickup.lon))
    curr_chunk = curr_chunk.replace("LATITUDE2", str(medkit_dropoff.lat))
    curr_chunk = curr_chunk.replace("LONGITUDE2", str(medkit_dropoff.lon))
    output_mission += curr_chunk
else:
    print("Not embedding medkit stuff because a poi wasn't provided.")

if smores_pickup is not None and smores_dropoff is not None:
    print("Embedding smores stuff...")
    curr_chunk = (chunk + '.')[:-1] # Clones the string
    curr_chunk = curr_chunk.replace("LATITUDE1", str(smores_pickup.lat))
    curr_chunk = curr_chunk.replace("LONGITUDE1", str(smores_pickup.lon))
    curr_chunk = curr_chunk.replace("LATITUDE2", str(smores_dropoff.lat))
    curr_chunk = curr_chunk.replace("LONGITUDE2", str(smores_dropoff.lon))
    output_mission += curr_chunk
else:
    print("Not embedding smores stuff because a poi wasn't provided.")

if bottle_pickup is not None and bottle_dropoff is not None:
    print("Embedding bottle stuff...")
    curr_chunk = (chunk + '.')[:-1] # Clones the string
    curr_chunk = curr_chunk.replace("LATITUDE1", str(bottle_pickup.lat))
    curr_chunk = curr_chunk.replace("LONGITUDE1", str(bottle_pickup.lon))
    curr_chunk = curr_chunk.replace("LATITUDE2", str(bottle_dropoff.lat))
    curr_chunk = curr_chunk.replace("LONGITUDE2", str(bottle_dropoff.lon))
    output_mission += curr_chunk
else:
    print("Not embedding bottle stuff because a poi wasn't provided.")

# RTL
output_mission += "INDEX	0	3	20	0.00000000	0.00000000	0.00000000	0.00000000	0.00000000	0.00000000	0.000000	1\n"

# Fix the indexes
indexes_to_fill = output_mission.count("INDEX")
for _ in range(indexes_to_fill):
    output_mission = output_mission.replace("INDEX", str(curr_idx), 1)
    curr_idx += 1

Path("out.waypoints").touch()
Path("out.waypoints").write_text(output_mission)

print("Done!")
sleep(999999)