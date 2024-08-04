import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os
import sys
from tqdm import tqdm
from deepgram import (
    Deepgram,
    DeepgramClient,
    PrerecordedOptions,
)
from pydub import AudioSegment
import zipfile
import shutil
import glob
import argparse
from openai import OpenAI
from loguru import logger
load_dotenv()

def _check_if_exists(path):
    if not os.path.exists(path):
        return False
    return True

def organizer(path_to_current, debug = False):
    # make sure the folders exist
    if not os.path.exists(f"{path_to_current}"):
        logger.debug(f"Creating {path_to_current}")
        if not debug:
            os.makedirs(f"{path_to_current}")
            os.makedirs(f"{path_to_current}/audio_chunks")

def extract_audio_from_zip(path_to_audio, path_to_current, debug = False):
    if os.path.isdir(path_to_audio):
        if debug:
            logger.error(f"{path_to_audio} is a directory")
        return False
    if glob.glob(f"{path_to_current}/*yak*") or glob.glob(f"{path_to_current}/*Yak*"):
        logger.info("Audio already extracted")
        return True
    with zipfile.ZipFile(path_to_audio, 'r') as zip_ref:
        logger.info(f"Extracting {path_to_audio}")
        for name in zip_ref.namelist():
            # if there is a folder, we have to go one level deeper first
            if "/" in name:
                for sub_name in zip_ref.namelist():
                    dir_name = sub_name.split("/")[0]
                    file_name = sub_name.split("/")[-1]
                    if not debug:
                        if "yak" in file_name.lower():
                            zip_ref.extract(sub_name, path=path_to_current)
                            os.rename(f"{path_to_current}/{sub_name}", f"{path_to_current}/{file_name}")
                            shutil.rmtree(f"{path_to_current}/{dir_name}")
            elif "yak" in name.lower():
                if not debug:
                    zip_ref.extract(name, path=path_to_current)
        logger.info("Extraction complete")
        return True

# take the audio file and split it into chunks of 30-60 mins
# then upload each chunk to deepgram
# then save the results to a file
def split_audio_into_chunks(path_to_current, debug = False, verbose = False):
    # send via buffer so no storage is necessary
    # find the file that contains "yak" in it
    logger.info(f"Splitting audio into chunks")
    path_to_dir_chunks= f"{path_to_current}audio_chunks/"
    files = glob.glob(f"{path_to_current}/*yak*")
    if not files:
        files = glob.glob(f"{path_to_current}/*Yak*")
        if not files:
            logger.info("No audio with 'yak' in it")
            return
    if verbose:
        logger.debug(f"Path to audio: {path_to_current}")
        logger.debug(f"Path to chunks: {path_to_dir_chunks}")
    count = 0
    desired_audio_length = int(os.getenv("DESIRED_AUDIO_LENGTH", str(30 * 60 * 1000)))
    start = 0
    if _check_if_exists(path_to_dir_chunks):
        if len(os.listdir(path_to_dir_chunks)) > 0:
            logger.info("Chunks already exist")
            test_audio = AudioSegment.from_file(f"{path_to_dir_chunks}chunk_1.wav")
            if len(test_audio) == desired_audio_length:
                logger.info("Chunks are correct length")
                return
            else:
                logger.info("Chunks are not correct length")
                # shutil.rmtree(path_to_dir_chunks)
                # os.makedirs(path_to_dir_chunks)
    if debug:
        logger.info("Splitting complete")
        return
    audio = AudioSegment.from_file(files[0])
    while start < len(audio):
        end = start + desired_audio_length
        if end > len(audio):
            end = len(audio)
        chunk: AudioSegment = audio[start:end]
        count += 1
        chunk.export(f"{path_to_dir_chunks}chunk_{count}.wav", format="wav")
        start = end
    logger.info("Splitting complete")

def _fetch_with_retry(deepgram, payload, options, result_file, attempt):
    try:
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)
        logger.info(f"Deepgram Transcription response attempt {attempt}")
        text = response['results']['channels'][0]['alternatives'][0]['transcript']
        result_file.write(text)
        logger.info(f"Deepgram Transcription finished")
        return True
    except Exception as e:
        logger.error(f"Exception: {e}")
    return False

def deepgram_transcription(path_to_current, token, debug = False, verbose = False):
    logger.info(f"Deepgram Transcription started")
    path_to_dir_chunks = f"{path_to_current}audio_chunks/"
    if verbose:
        logger.debug(f"Path to transcript: {path_to_current}")
        logger.debug(f"Path to chunks: {path_to_dir_chunks}")
        logger.debug(f"Total number of files: {len(os.listdir(path_to_dir_chunks))}")
    if _check_if_exists(f"{path_to_current}deepgram-transcription.txt"):
        logger.info("Transcription already exists")
        if os.stat(f"{path_to_current}deepgram-transcription.txt").st_size == 0:
            logger.info("Transcription file is empty")
        else:
            return
    if debug:
        logger.info(f"Deepgram Transcription finished")
        return
    deepgram = DeepgramClient()
    options = PrerecordedOptions(
        model="nova-2",
        smart_format=True,
        punctuate=True,
    )
    with open(f"{path_to_current}deepgram-transcription.txt", "a") as res:
        for file in sorted(os.listdir(path_to_dir_chunks)):
            logger.info(f"Working on chunk {file}")
            for i in range(3):
                with open(f"{path_to_dir_chunks}{file}", "rb") as f:
                    payload = {
                        "buffer": f,
                    }
                    if _fetch_with_retry(deepgram, payload, options, res, i):
                        break

def openai_massage(path_to_current, path_to_prev, debug = False, verbose = False):
    desired_summary_name = os.getenv("DESIRED_SUMMARY_NAME", "summary")
    model = os.getenv("OPENAI_MODEL", None)
    if not model:
        logger.error("Model not found")
        raise Exception("Model not found")
    if _check_if_exists(f"{path_to_current}{desired_summary_name}.txt"):
        logger.info("Summary already exists")
        return
    with open(f"{os.path.dirname(__file__)}/prompt_file.txt", "r") as f:
        prompt = f.read()
    logger.info(f"OpenAI massage start")
    if path_to_prev:
        try:
            with open(f"{path_to_prev}{desired_summary_name}.txt", "r") as f:
                prompt += "\nPrevious Session Summary: \n"
                for line in f:
                    prompt += line
        except Exception as e:
            logger.error(f"Exception: {e}")
    messages = [
        {"role": "system", "content": prompt},
    ]
    if verbose:
        logger.debug(f"Path to transcript {path_to_current}")
        logger.debug(f"Path to previous transcript {path_to_prev}")
        logger.debug(f"Messages: {messages}")
        logger.debug(f"Prompt: {prompt}")
    if debug:
        logger.info(f"OpenAI massage end")
        return
    with open(f"{path_to_current}deepgram-transcription.txt", "r") as res:
        text = res.read()
        messages.append({"role": "user", "content": text})
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    response = client.chat.completions.create(model = model, messages = messages)
    with open(f"{path_to_current}{desired_summary_name}.txt", "w") as file:
        file.write(response.choices[0].message.content)
        logger.info(f"OpenAI massage end")

def _get_last_session(session_name):
    session_num = int(session_name.split(" ")[-1])
    if(session_num <= 9):
        return None
    return f"session {session_num - 1}"

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
    prev_session_name = _get_last_session(session_name)
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
