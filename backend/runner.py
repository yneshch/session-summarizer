from datetime import datetime
from dotenv import load_dotenv
import os
import sys
from loguru import logger

from backend.transcription.transcriber_dg import extract_audio_from_zip, split_audio_into_chunks, deepgram_transcription
from backend.summarization.summerizer_openai import openai_massage
from backend.utils.shared_utils import check_if_exists
from backend.constants import DEBUG, VERBOSE, DESIRED_SUMMARY_NAME, OPENAI_MODEL

load_dotenv()

logger.remove()
if DEBUG:
    logger.add(sys.stderr)
else:
    logger.add(f"logs/transcriber_{datetime.now().strftime('%Y_%m_%d')}.log", rotation="1 MB")

#TODO: Check if this makes sense vs the one in api.py
def get_session_from_name(session_name):
    session_num = int(session_name.split(" ")[-1])
    if(session_num <= 9):
        return None
    return f"session {session_num - 1}"

def organizer(path_to_current):
    if not check_if_exists(path_to_current):
        logger.debug(f"Creating {path_to_current}")
        if not DEBUG:
            os.makedirs(f"{path_to_current}")
            os.makedirs(f"{path_to_current}/audio_chunks")

def runner(file_name, path_to_all_recodings, path_to_dir_transcript):
    session_name = file_name.split(".")[0]
    prev_session_name = get_session_from_name(session_name)
    path_to_current = f"{path_to_dir_transcript}/{session_name}/" 
    path_to_prev = f"{path_to_dir_transcript}/{prev_session_name}/" if prev_session_name else None
    logger.info("*"*20)
    logger.info(f"Starting session {session_name}")
    path_to_recording = f"{path_to_all_recodings}/{session_name}.zip"
    if VERBOSE:
        logger.debug(f"Session Name: {session_name}")
        logger.debug(f"Previous Session Name: {prev_session_name}")
        logger.debug(f"Path to Audio: {path_to_recording}")
        logger.debug(f"Path to Transcript: {path_to_current}")
        logger.debug(f"Path to Previous Transcript: {path_to_prev}")
        logger.debug(f"Debug: {DEBUG}")
    try:        
        organizer(path_to_current)
        if not (extract_audio_from_zip(path_to_recording, path_to_current)):
            logger.info("Exiting due not not having a file to transcribe")
            return
        split_audio_into_chunks(path_to_current)
        deepgram_transcription(path_to_current)
        openai_massage(path_to_current, path_to_prev, DESIRED_SUMMARY_NAME, OPENAI_MODEL)
    except Exception as e:
        logger.error(f"Exception: {e}")
        raise e
    logger.info(f"Session {session_name} completed")
