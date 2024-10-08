import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()

DEBUG = (os.getenv("DEBUG_MODE").lower() == 'true')
VERBOSE = (os.getenv("VERBOSE_MODE").lower() == 'true')

IS_WINDOWS_MACHINE = os.name == 'nt'

if IS_WINDOWS_MACHINE:
    BASE_PATH = Path(os.getenv("BASE_PATH")).as_posix()
    TRANSCRIPT_PATH = Path(os.getenv("TRANSCRIPT_PATH")).as_posix()
else:
    BASE_PATH = Path(os.getenv("BASE_PATH"))
    TRANSCRIPT_PATH = Path(os.getenv("TRANSCRIPT_PATH"))
DESIRED_SUMMARY_NAME = os.getenv("DESIRED_SUMMARY_NAME", "summary")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", None)
