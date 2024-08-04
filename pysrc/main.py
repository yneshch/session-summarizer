from typing import Union

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from loguru import logger
load_dotenv()

app = FastAPI()

@app.get("/")
def read_root():
    return "healthy"

def _extract_session_number(path):
    path_to_dir_transcript = os.getenv("TRANSCRIPT_PATH")
    if os.path.isdir(f"{path_to_dir_transcript}/{path}"):
        return int(path.split(" ")[-1])
    return -1

@app.get("/get_all_transcript_paths")
def get_all_transcript_paths():
    path_to_dir_transcript = os.getenv("TRANSCRIPT_PATH")
    possible_transcript_paths = []
    sorted_list = [f"{path_to_dir_transcript}/{path}" for path in sorted(os.listdir(path_to_dir_transcript), key= _extract_session_number)]
    for path in sorted_list:
        if os.path.isdir(path):
            possible_transcript_paths.append(path)
    return possible_transcript_paths

# TODO: add debug mode
@app.get("/run_transcriber_all")
def run_transcriber_all():
    os.system(f"python3 /app/pysrc/transcriber_v2.py -a")
    return "ok"

@app.get("/run_transcriber_single/")
def run_transcriber_single(session_number: int):
    os.system(f"python3 /app/pysrc/transcriber_v2.py -s {session_number}")
    return "ok"

@app.get("/run_transcriber_batch/")
def run_transcriber_batch(batch_size: int, session_number: int|None = None):
    if  session_number is not None:
        os.system(f"python3 /app/pysrc/transcriber_v2.py -b {batch_size} -s {session_number}")
    else:
        os.system(f"python3 /app/pysrc/transcriber_v2.py -b {batch_size}")
    return "ok"
