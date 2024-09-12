from typing import Optional, Union

import os
from fastapi import FastAPI
from loguru import logger

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from utils.runner import runner
from utils.constants import DEBUG, BASE_PATH
from utils.api_utils import _extract_session_number

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

class TranscriptionRequest(BaseModel):
    session_name: Optional[str]
    # file_path: Optional[str]

class TranscriptionResponse(BaseModel):
    message: str

@app.get("/")
def read_root():
    return "healthy"

@app.get("/get_all_files_to_transcribe")
def get_all_files_to_transcribe():
    possible_transcript_paths = []
    sorted_list = [f"{BASE_PATH}/{path}" for path in sorted(os.listdir(BASE_PATH), key= _extract_session_number)]
    for path in sorted_list:
        if os.path.isdir(path):
            possible_transcript_paths.append(path)
    return possible_transcript_paths

@app.post("/run_transcriber_single/")
def run_transcriber_single(session_name: str):
    if DEBUG:
        logger.debug(f"{session_name}")
    try:
        # TODO: Need to find file
        runner(f"{TRANSCRIPT_PATH}/{session_name}", os.getenv("BASE_PATH"), os.getenv("TRANSCRIPT_PATH"))
        return "ok"
    except Exception as e:
        logger.error(f"Error running transcriber: {e}")
        return "error"

@app.post("/run_transcriber_single_file/", response_model=TranscriptionResponse)
def run_transcriber_single(request: TranscriptionRequest):
    file_path = request.session_name
    if not file_path:
        return TranscriptionResponse(message="error")
    if DEBUG:
        logger.debug(f"{file_path}")
    try:
        runner(file_path, os.getenv("BASE_PATH"), os.getenv("TRANSCRIPT_PATH"))
        return TranscriptionResponse(message="ok")
    except Exception as e:
        logger.error(f"Error running transcriber: {e}")
        return TranscriptionResponse(message="error")
