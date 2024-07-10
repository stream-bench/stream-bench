import time
import groq
import openai
import together
import anthropic
import google.api_core.exceptions as g_exceptions
import urllib.request
from colorama import Fore, Style

def retry_with_exponential_backoff(
    func,
    initial_delay: float = 0.25,
    exponential_base: float = 2,
    max_retries: int = 10
):
    # Define errors based on available libraries.
    errors_tuple = (
        openai.RateLimitError, openai.APIError,
        g_exceptions.ResourceExhausted, g_exceptions.ServiceUnavailable, g_exceptions.GoogleAPIError,
        anthropic.BadRequestError, anthropic.InternalServerError, anthropic.RateLimitError,
        urllib.error.HTTPError, urllib.error.URLError,
        groq.RateLimitError, groq.InternalServerError, groq.APIConnectionError,
        together.error.TogetherException,
        ValueError, IndexError, UnboundLocalError
    )
    """Retry a function with exponential backoff."""
    def wrapper(*args, **kwargs):
        # Initialize variables
        num_retries = 0
        delay = initial_delay
        # Loop until a successful response or max_retries is hit or an exception is raised
        while True:
            try:
                return func(*args, **kwargs)
            # Retry on specific errors
            except errors_tuple as e:
                # Increment retries
                num_retries += 1
                # Check if max retries has been reached
                if isinstance(e, ValueError) or (num_retries > max_retries):
                    print(Fore.RED + f"ValueError / Maximum number of retries ({max_retries}) exceeded." + Style.RESET_ALL)
                    result = 'error:{}'.format(e)
                    prompt = kwargs["prompt"] if "prompt" in kwargs else args[1]
                    res_info = {
                        "input": prompt,
                        "output": result,
                        "num_input_tokens": len(prompt) // 4,  # approximation
                        "num_output_tokens": 0,
                        "logprobs": []
                    }
                    return result, res_info
                # Sleep for the delay
                print(Fore.YELLOW + f"Error encountered ({e}). Retry ({num_retries}) after {delay} seconds..." + Style.RESET_ALL)
                time.sleep(delay)
                # Increment the delay
                delay *= exponential_base
            # Raise exceptions for any errors not specified
            except Exception as e:
                raise e
    return wrapper
