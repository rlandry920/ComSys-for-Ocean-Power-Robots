from enum import Enum

# CommMode.py
#
# Last updated: 04/12/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Enumerated type values to represented states of communication system.

class CommMode(Enum):
    HANDSHAKE = 0,
    RADIO = 1,
    SATELLITE = 2,
    DEBUG = 3