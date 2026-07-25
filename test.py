import pydirectinput
import time

# Give yourself 3 seconds to switch windows into Minecraft
time.sleep(3)

# Perform a hardware-level left click
# print( "simple clic" )
# pydirectinput.leftClick()
# time.sleep(3)

# Alternatively, for holding down a click to mine/attack:
print( "holding" )
pydirectinput.mouseDown( button="right" )
time.sleep( 0.0000000001 )
pydirectinput.mouseUp( button="right" )
