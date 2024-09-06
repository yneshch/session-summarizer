from datetime import datetime
from dotenv import load_dotenv
import os
import sys
from tqdm import tqdm
import argparse
from loguru import logger
from backend.transcription.deepgram import extract_audio_from_zip, split_audio_into_chunks, deepgram_transcription
from backend.summarization.openai import openai_massage
from backend.utils.shared_utils import check_if_exists

load_dotenv()

#TODO: Check if this makes sense vs the one in api.py
def get_session_from_name(session_name):
    session_num = int(session_name.split(" ")[-1])
    if(session_num <= 9):
        return None
    return f"session {session_num - 1}"

def organizer(path_to_current, debug = False):
    if not check_if_exists(path_to_current):
        logger.debug(f"Creating {path_to_current}")
        if not debug:
            os.makedirs(f"{path_to_current}")
            os.makedirs(f"{path_to_current}/audio_chunks")

def main_loop(path_to_all_recodings, path_to_current, path_to_prev, session_name, prev_session_name, debug, verbose, skip_input):
    path_to_recording = f"{path_to_all_recodings}/{session_name}.zip"
    if verbose:
        logger.debug(f"Session Name: {session_name}")
        logger.debug(f"Previous Session Name: {prev_session_name}")
        logger.debug(f"Path to Audio: {path_to_recording}")
        logger.debug(f"Path to Transcript: {path_to_current}")
        logger.debug(f"Path to Previous Transcript: {path_to_prev}")
        logger.debug(f"Debug: {debug}")
    if not skip_input:
        ender = input(f"Do you want to proceed with transcription of {session_name}? ([y]/n)")
        if ender == "":
            ender = "y"
        if ender.lower() != "y":
            logger.info("Exiting")
            return
    try:        
        organizer(path_to_current, debug)
        if not (extract_audio_from_zip(path_to_recording, path_to_current, debug)):
            logger.info("Exiting due not not having a file to transcribe")
            return
        split_audio_into_chunks(path_to_current, debug, verbose)
        deepgram_transcription(path_to_current, token, debug, verbose)
        openai_massage(path_to_current, path_to_prev, debug, verbose)
    except Exception as e:
        logger.error(f"Exception: {e}")
        raise e

def runner(file_name, path_to_all_recodings, path_to_dir_transcript, debug, verbose, skip_input = False):
    session_name = file_name.split(".")[0]
    prev_session_name = get_session_from_name(session_name)
    path_to_current = f"{path_to_dir_transcript}/{session_name}/" 
    path_to_prev = f"{path_to_dir_transcript}/{prev_session_name}/" if prev_session_name else None
    logger.info("*"*20)
    logger.info(f"Starting session {session_name}")
    main_loop(path_to_all_recodings, path_to_current, path_to_prev,session_name, prev_session_name, debug, verbose, skip_input)
    logger.info(f"Session {session_name} completed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcriber script")
    parser.add_argument('-s',"--session", type=int, help="Session number to transcribe")
    parser.add_argument('-b',"--batch", type=int, help="Number of sessions to transcribe")
    parser.add_argument('-d',"--debug", action='store_true', help="Debug mode")
    parser.add_argument('-v',"--verbose", action='store_true', help="Verbose mode")
    parser.add_argument('-a',"--all", action='store_true', help="Transcribe all sessions")
    args = parser.parse_args()

    logger.remove()
    if args.debug:
        logger.add(sys.stderr)
    else:
        logger.add(f"logs/transcriber_{datetime.now().strftime('%Y_%m_%d')}.log", rotation="1 MB")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    token  = os.getenv("DEEPGRAM_API_KEY")
    path_to_all_recodings = os.getenv("BASE_PATH", None) #better pathing
    path_to_dir_transcript = os.getenv("TRANSCRIPT_PATH", None) #better pathing
    if not token:
        logger.error("Deepgram token not found")
        raise Exception("Deepgram token not found")
    if not path_to_all_recodings or not path_to_dir_transcript:
        logger.error("Path to recording or transcript not found")
        raise Exception("Path to recording or transcript not found")
    if args.all or args.batch:
        files = sorted(
            os.listdir(f"{path_to_all_recodings}")                   ,
            key= lambda x: int(x.split(" ")[-1].split(".")[0])
        )
        start = max(args.session-9, 0) if args.session else 0
        batch = args.batch + start if args.batch and (args.batch + start <= len(files)) else len(files)
        if args.debug:
            for recording in files[start:batch]:
                if ".zip" not in recording:
                    continue
                runner(recording, path_to_all_recodings, path_to_dir_transcript, args.debug, args.verbose, skip_input = True)
        else:
            for recording in tqdm(files[start:batch]):
                if ".zip" not in recording:
                    continue
                runner(recording, path_to_all_recodings, path_to_dir_transcript, args.debug, args.verbose, skip_input = True)
    elif not args.all and args.session:
        session_name = f"session {args.session}"
        runner(session_name, path_to_all_recodings, path_to_dir_transcript, args.debug, args.verbose)
    else:
        logger.info("Invalid session number")
        logger.info("Exiting")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("-"*20)
