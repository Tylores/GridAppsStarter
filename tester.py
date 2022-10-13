from gridappsd import GridAPPSD
import os # Set username and password
os.environ['GRIDAPPSD_USER'] = 'tutorial_user'
os.environ['GRIDAPPSD_PASSWORD'] = '12345!'
os.environ['GRIDAPPSD_ADDRESS'] = 'localhost'
os.environ['GRIDAPPSD_PORT'] = '61613'

# Connect to GridAPPS-D Platform
gapps = GridAPPSD()
assert gapps.connected
