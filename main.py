import sys
import telnetlib
import psutil
import signal
import emoji
from termcolor import colored
from time import sleep
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

## Tool configuration
mapname = "cache"  # used for output file name
gridWidth = 35  # width of the grid of points to test
gridHeight = 30  # height ... (each point ~ 9sec)
# bomb location in in-game coordinates - use 'getpos' console command (possibly need to subtract 20-30 to not clip in the ceiling)
bomb_poss = [(204.968750, -1114.031250, 1703.093750), (204.968750, -1454.968750, 1703.093750),
             (-325.957367, -1454.968750, 1736.093750), (-324.637268, -1042.984497, 1736.093750)]
bomb_angles = [(19.366396, 75.690216, 0.000000), (7.922823, -57.091469, 0.000000), (49.837845, -83.500259, 0.000000),
               (75.569008, 36.046520, 0.000000)]
kevlar = True
# area of the map to cover
minX = -1833
maxX = 3374
minY = -1515
maxY = 2438
# first z value (in steps of 100 units from minZ to maxZ) to be inbounds used for each (x,y) coordinate to test
minZ = 1600
maxZ = 2100
# Radar map bounding pixels in the image
radar_img = "cache.png"
radarStartCol = 35
radarEndCol = 962
radarStartRow = 181
radarEndRow = 855

timescale = 4.0
fillSize = 10

# Config
tn_host = "127.0.0.1"
tn_port = "2121"


def tp(tn, pos, angle):
    run(tn, f"setpos {pos[0]} {pos[1]} {pos[2]}; setang {angle[0]} {angle[1]} {angle[2]};")
    sleep(0.010)


def plant(tn):
    run(tn, "give weapon_c4")
    sleep(0.005)
    run(tn, "slot5")
    sleep(0.005)
    run(tn, "+attack")
    sleep(5 / timescale * 1.7)
    run(tn, "-attack")
    sleep(0.005)


def getPosLine(tn):
    run(tn, "getpos")
    tn.read_until(b"setpos ")
    str = b"setpos "
    while True:
        c = tn.read_some()
        str += c
        if c.__contains__(b"\r\n"):
            break
    str = str.replace(b"\r", b"").replace(b"\n", b"")
    return str


def isInbouds(tn, pos, angle):
    retpos = getPosLine(tn)
    tp(tn, pos, angle)
    found = tn.read_until(b"setpos into world, use noclip to unstick yourself!", 1)
    if found.__contains__(b"setpos into world, use noclip to unstick yourself!"):
        inbounds = False
    else:
        inbounds = True
    run(tn, retpos.decode("ascii"))
    sleep(0.005)
    return inbounds


def findValidHeight(tn, x, y):
    minZ = 1600
    maxZ = 2100
    z = minZ
    zStep = 100
    while z <= maxZ:
        if isInbouds(tn, (x, y, z), (0, 0, 0)):
            return z
        z += zStep
    return -1


def signal_handler(signal, frame):
    print("\nquitting...")
    sys.exit(0)


# Print with emojis
def print_e(message):
    print(colored(emoji.emojize(message, use_aliases=True), attrs=['bold']))


# List PIDs of processes matching processName
def processExists(processName):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() == processName.lower():
            return True
    return False


def mapIdxToPixel(coord, pixelBounds):
    pixelMinRow, pixelMaxRow, pixelMinCol, pixelMaxCol = pixelBounds
    virtSizeX = (pixelMaxCol - pixelMinCol) * ((gridWidth + 1) / gridWidth)
    virtSizeY = (pixelMaxRow - pixelMinRow) * ((gridHeight + 1) / gridHeight)
    pixelCol = pixelMinCol + (coord[0]) * (virtSizeX / gridWidth)
    pixelRow = pixelMinRow + (gridHeight - coord[1] - 1) * (virtSizeY / gridHeight)
    return int(pixelRow), int(pixelCol)


def addDmgCircle(transp, dmg, pixel):
    drawTemp = ImageDraw.Draw(transp, "RGBA")
    if dmg >= 100:
        drawTemp.ellipse(
            (pixel[1] - fillSize, pixel[0] - fillSize, pixel[1] + fillSize, pixel[0] + fillSize),
            fill=(255, 0, 0), outline=(255, 255, 255, 128), width=1)
    elif dmg > 0:
        color = int(max(min(dmg, 100) * 1.5, 50)) + 50  # map dmg to colour
        drawTemp.ellipse(
            (pixel[1] - fillSize, pixel[0] - fillSize, pixel[1] + fillSize, pixel[0] + fillSize),
            fill=(0, color, 0), outline=(255, 255, 255, 128), width=1)
    else:
        drawTemp.ellipse(
            (pixel[1] - fillSize, pixel[0] - fillSize, pixel[1] + fillSize, pixel[0] + fillSize),
            fill=(0, 0, 0, 0), outline=(255, 255, 255, 128), width=1)


# Runs commands on the csgo console
def run(txn, command):
    cmd_s = command + "\n"
    txn.write(cmd_s.encode('utf-8'))
    sleep(0.005)


signal.signal(signal.SIGINT, signal_handler)


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            print(colored("Run with no arguments to initiate and connect to csgo", attrs=['bold']))
            print(colored(
                "Make sure you set up csgo to receive connections with this launch option: -netconport " + str(tn_port),
                attrs=['bold']))

    # Make sure cs:go is running before trying to connect
    if not processExists("csgo.exe"):
        print_e(":information: Waiting for csgo to start... ")
        while not processExists("csgo.exe"):
            sleep(0.25)
        sleep(10)

    # Initialize csgo telnet connection
    print_e(":information: Trying " + tn_host + ":" + tn_port + "...")
    try:
        tn = telnetlib.Telnet(tn_host, tn_port)
    except ConnectionRefusedError:
        # Retry in 10 seconds
        sleep(10)
        pass
    try:
        tn = telnetlib.Telnet(tn_host, tn_port)
    except ConnectionRefusedError:
        print_e(":x: Connection refused. Make sure you have the following launch option set:")
        print(colored("  -netconport " + str(tn_port), attrs=['bold']))
        sys.exit(1)
    tn.write(b"echo CSCTL Active, use exectn instruction_file to execute commands\n")
    tn.read_until(b"commands")
    print_e(":heavy_check_mark: Successfully Connected")

    while True:
        print_e(":information: Listening for command from console")
        # Capture console output until we encounter our exec string
        tn.read_until(b"mapbomb ")
        run(tn, "endround")

        global mapname
        global minX
        global maxX
        global minY
        global maxY
        global gridWidth
        global kevlar
        global radar_img

        # values used to spread the points evenly across the map
        virtSizeX = (maxX - minX) * ((gridWidth + 1) / gridWidth)
        virtSizeY = (maxY - minY) * ((gridHeight + 1) / gridHeight)
        xStep = virtSizeX / gridWidth
        yStep = virtSizeY / gridHeight

        for bombIdx in range(len(bomb_poss)):
            bomb_position = bomb_poss[bombIdx]
            bomb_angle = bomb_poss[bombIdx]

            image = [[-1] * gridWidth for i in range(gridHeight)]  # the dmg values received at the coords

            for xIdx in range(gridWidth):
                for yIdx in range(gridHeight):
                    x = minX + xStep * xIdx
                    y = minY + yStep * yIdx
                    res = findValidHeight(tn, x, y)
                    if res == -1:
                        res = minZ
                    tp(tn, bomb_position, bomb_angle)
                    plant(tn)
                    tp(tn, (x, y, res), (0, 0, 0))
                    if kevlar:
                        run(tn, "give item_kevlar")
                    sleep(10.5 / timescale * 2.1)
                    run(tn, "endround")
                    sleep(0.005)

                    readStr = tn.read_until(b"Damage Taken from \"World\" - ", 1 / timescale)
                    if readStr.__contains__(b"Damage Taken from \"World\" - "):
                        dmg = int(tn.read_until(b" "))
                    else:
                        dmg = 0
                    progressPercentage = ((xIdx * gridWidth + yIdx) / (gridWidth * gridWidth)) * 100
                    print("(" + str(x) + ", " + str(y) + "): " + str(dmg) + "dmg - " + str(progressPercentage) + "%")
                    image[yIdx][xIdx] = dmg
            print(image)

            # Output image generation
            print("Starting output image generation")
            radar = Image.open(radar_img).convert("RGBA")
            drawer = ImageDraw.Draw(radar, "RGBA")

            pixelBounds = (radarStartRow, radarEndRow, radarStartCol, radarEndCol)
            for row in range(gridHeight):
                print("row: " + str(row) + "/" + str(gridWidth - 1))
                for col in range(gridWidth):
                    dmg = image[row][col]
                    pixel = mapIdxToPixel((col, row), pixelBounds)

                    transp = Image.new("RGBA", radar.size, (0, 0, 0, 0))
                    addDmgCircle(transp, dmg, pixel)

                    radar.paste(Image.alpha_composite(radar, transp))
                    font = ImageFont.truetype("arial.ttf", 10)
                    w, h = drawer.textsize(str(dmg), font=font)
                    drawer.text((pixel[1] - w / 2, pixel[0] - h / 2), str(dmg), fill="white", font=font)

            radar.save(f"output/{mapname}_bombloc{str(bombIdx)}_{str(gridWidth)}x{str(gridHeight)}.png", "PNG")


if __name__ == "__main__":
    main()
