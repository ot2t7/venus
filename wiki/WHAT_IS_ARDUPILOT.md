# What the heck is an ArduPilot anyways?
This page will contain some definitions and clarifications on the ArduPilot ecosystem and the hardware it's gonna run on.

## What is ArduPilot?
ArduPilot is a bunch of software written by the ArduPilot team. It's an ecosystem which allows you to operate and automate drones, and other cool stuff (ArduPilot has software for RC submarines!). We're gonna use ArduPilot for a quadcopter, so we'll be using a software package part of ArduPilot, called ArduCopter (What's ArduCopter? It will be explained below).
## What is a flight controller?
A flight controller is just a microcontroller with some extra features. Have you ever heard/used a raspberry pi pico/ESP32/arduino uno? A flight controller isn't very much different from any of them, it's just a small computer we use to run a program. The difference is, flight controllers are a little more powerful, and have some useful instruments for flight built right into the board, like barometers, accelerometers, etc.
## What is ArduCopter?
ArduCopter is some software part of the ArduPilot project. ArduCopter is a firmware for flight controllers. This means it's a little operating system that will run on a flight controller and read instruments, control motors, recieve and process remote control input, automate basic tasks and crucially it can **run custom scripts.** 
## What is Mission Planner?
Mission planner is some software part of the ArduPilot project. It's a desktop/laptop application which allows a pilot to interface with a flight controller running ArduCopter. Mission Planner provides a way to create automated sequences of actions to be sent to the copter, it can display the copter's current position and it's telemetry (all the statistics about the drone's flight and instruments), and it can also upload the aforementioned custom scripts. Mission Planner is the main ground control software we'll be using, like an air traffic control system all in one app. Pretty cool!
