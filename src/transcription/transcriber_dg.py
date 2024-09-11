import os
from loguru import logger
import glob
import zipfile
import shutil
from utils.shared_utils import check_if_exists
from pydub import AudioSegment
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
)
from utils.constants import DEBUG, VERBOSE

def extract_audio_from_zip(path_to_audio, path_to_current):
    if os.path.isdir(path_to_audio):
        if DEBUG:
            # if in debug mode, don't actually extract the audio
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
                    if not DEBUG:
                        if "yak" in file_name.lower():
                            zip_ref.extract(sub_name, path=path_to_current)
                            os.rename(f"{path_to_current}/{sub_name}", f"{path_to_current}/{file_name}")
                            shutil.rmtree(f"{path_to_current}/{dir_name}")
            elif "yak" in name.lower():
                if not DEBUG:
                    zip_ref.extract(name, path=path_to_current)
        logger.info("Extraction complete")
        return True
    
def split_audio_into_chunks(path_to_current):
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
    if VERBOSE:
        logger.debug(f"Path to audio: {path_to_current}")
        logger.debug(f"Path to chunks: {path_to_dir_chunks}")
    count = 0
    desired_audio_length = int(os.getenv("DESIRED_AUDIO_LENGTH", str(30 * 60 * 1000)))
    start = 0
    if not DEBUG and check_if_exists(path_to_dir_chunks):
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
    if DEBUG:
        # if in debug mode, don't actually split the audio
        logger.info("Running splitting audio in debug mode, not actually splitting")
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

def deepgram_transcription(path_to_current):
    logger.info(f"Deepgram Transcription started")
    path_to_dir_chunks = f"{path_to_current}audio_chunks/"
    if VERBOSE:
        logger.debug(f"Path to transcript: {path_to_current}")
        logger.debug(f"Path to chunks: {path_to_dir_chunks}")
        logger.debug(f"Total number of files: {len(os.listdir(path_to_dir_chunks))}")
    if not DEBUG and check_if_exists(f"{path_to_current}deepgram-transcription.txt"):
        logger.info("Transcription already exists")
        if os.stat(f"{path_to_current}deepgram-transcription.txt").st_size == 0:
            logger.info("Transcription file is empty")
        else:
            return
    if DEBUG:
        # if in debug mode, don't actually transcribe
        logger.info(f"Running deepgram in debug mode, not sending request")
        return
    client = DeepgramClient() # gets from DEEPGRAM_API_KEY env variable
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
                    if _fetch_with_retry(client, payload, options, res, i):
                        break
