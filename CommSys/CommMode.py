from enum import Enum


class CommMode(Enum):
    HANDSHAKE = 0,
    RADIO = 1,
    SATELLITE = 2,
    DEBUG = 3