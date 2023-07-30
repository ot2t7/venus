# Venus

Venus is a guidance system for ArduPilot powered sUAS. This repository includes the guidance system, aswell as many image recognition algorithms powering it, and simulations. This repository included configuration for our own UAV, debug data, and waypoint missions, but most of it was removed as it contained some sensitive data, like GPS coordinates. 

* In `simulations`, there are some simulations we used to gather data.
* In `drone/main`, the actual guidance system resides.
* In `drone/venus-systemd`, the systemd service which starts the guidance system resides.
* In `drone/eye`, all of the image recognition work resides.
* In `missions`, ArduPilot missions and debug data resided.