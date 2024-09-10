import os
from loguru import logger
from openai import OpenAI
from backend.utils.shared_utils import check_if_exists
from backend.constants import DEBUG, VERBOSE
from backend.sample_prompt import SAMPLE_PROMPT

def openai_massage(path_to_current, path_to_prev, desired_summary_name, model):
    desired_summary_name = os.getenv("DESIRED_SUMMARY_NAME", "summary")
    model = os.getenv("OPENAI_MODEL", None)
    if not model:
        logger.error("Model not found")
        raise Exception("Model not found")
    if not DEBUG and check_if_exists(f"{path_to_current}{desired_summary_name}.txt"):
        logger.info("Summary already exists")
        return
    try:
        logger.debug(f"Opening prompt file")
        with open(f"{os.path.dirname(__file__)}/prompt_file.txt", "r") as f:
            prompt = f.read()
    except FileNotFoundError:
        logger.error("Prompt file not found, using sample prompt")
        prompt = SAMPLE_PROMPT
    except Exception as e:
        logger.error(f"Exception: {e}")
        raise e
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
    if VERBOSE:
        logger.debug(f"Path to transcript {path_to_current}")
        logger.debug(f"Path to previous transcript {path_to_prev}")
        logger.debug(f"Messages: {messages}")
        logger.debug(f"Prompt: {prompt}")
    if DEBUG:
        # If in debug mode, don't actually send the request
        logger.info(f"Running openai summary in debug mode, not sending request")
        return
    with open(f"{path_to_current}deepgram-transcription.txt", "r") as res:
        text = res.read()
        messages.append({"role": "user", "content": text})
    # gets from OPENAI_API_KEY env variable
    client = OpenAI() 
    response = client.chat.completions.create(model = model, messages = messages)
    with open(f"{path_to_current}{desired_summary_name}.txt", "w") as file:
        file.write(response.choices[0].message.content)
        logger.info(f"OpenAI massage end")
