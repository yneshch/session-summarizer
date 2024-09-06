import os
from loguru import logger

def check_if_exists(path):
    if not os.path.exists(path):
        return False
    return True

def get_session_from_name(session_name):
    session_num = int(session_name.split(" ")[-1])
    if(session_num <= 9):
        return None
    return f"session {session_num - 1}"

def organizer(path_to_current, debug = False):
    # make sure the folders exist
    if not os.path.exists(f"{path_to_current}"):
        logger.debug(f"Creating {path_to_current}")
        if not debug:
            os.makedirs(f"{path_to_current}")
            os.makedirs(f"{path_to_current}/audio_chunks")
