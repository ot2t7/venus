from math import tan, atan, radians, degrees


height = input("input height or input x if you want to solve for this: ")
frame = input("input frame width/height or input x if you want to solve for this: ")
fov = input("input fov or input x if you want to solve for this: ")

answer = 0
height = float(height) if height != "x" else height
frame = float(frame) if frame != "x" else frame
fov = float(fov) if fov != "x" else fov



if type(height) == str:
    answer = (frame/2)/(tan(radians(fov/2)))

elif type(frame) == str:
    answer = 2*(tan(radians(fov/2))*height)

elif type(fov) == str:
    answer = 2* degrees( atan(frame / (2 * height)) )

print (answer)
