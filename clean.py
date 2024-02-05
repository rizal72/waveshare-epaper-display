#!/usr/bin/python3
import sys
import os
import logging
import datetime
from PIL import Image
from utility import configure_logging

libdir = "./lib/e-Paper/RaspberryPi_JetsonNano/python/lib"
if os.path.exists(libdir):
    sys.path.append(libdir)

configure_logging()

# Dear future me: consider converting this to a WAVESHARE_VERSION variable instead if you ever intend to support more screen sizes.

waveshare_epd75_version = os.getenv("WAVESHARE_EPD75_VERSION", "2")

if (waveshare_epd75_version == "1"):
    from waveshare_epd import epd2in7 as epd7in5
elif (waveshare_epd75_version == "2B"):
    from waveshare_epd import epd2in7b_V2 as epd7in5
else:
    from waveshare_epd import epd2in7_V2 as epd7in5

try:
    epd = epd7in5.EPD()
    logging.info("Initialize screen")
    epd.init()
    logging.info("Clear screen")
    epd.Clear()
    logging.info("Sleeping epaper")
    epd.sleep()

except IOError as e:
    logging.exception(e)

except KeyboardInterrupt:
    logging.debug("Keyboard Interrupt - Exit")
    epd7in5.epdconfig.module_exit()
    exit()
