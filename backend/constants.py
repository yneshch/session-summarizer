import os

DEBUG = (os.getenv("DEBUG_MODE").lower() == 'true')
VERBOSE = (os.getenv("VERBOSE_MODE").lower() == 'true')
