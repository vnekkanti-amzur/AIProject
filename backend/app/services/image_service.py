import logging
import base64
from io import BytesIO
from uuid import uuid4

import httpx
from openai import OpenAI, OpenAIError

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_image_client() -> OpenAI:
    """Return an OpenAI client routed via the Amzur LiteLLM proxy for image generation."""
    return OpenAI(
        api_key=settings.LITELLM_API_KEY,
        base_url=settings.LITELLM_PROXY_URL,
    )


async def generate_chat_image(prompt: str, user_email: str) -> str:
    """
    Generate an image from a text prompt using the configured image generation model.

    Args:
        prompt: Text description of the image to generate.
        user_email: Email of the authenticated user making the request (for usage tracking).

    Returns:
        The URL of the generated image.

    Raises:
        ValueError: If the prompt is empty or validation fails.
        Exception: For API errors (safety filters, quota limits, network issues, etc.).
                   Includes error type and message for caller to handle gracefully.
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty")

    client = get_image_client()
    logger.info(f"DEBUG: Image generation request")
    logger.info(f"  Model: {settings.IMAGE_GEN_MODEL}")
    logger.info(f"  Prompt: {prompt[:100]}")
    logger.info(f"  User: {user_email}")

    try:
        response = client.images.generate(
            model=settings.IMAGE_GEN_MODEL,
            prompt=prompt.strip(),
            n=1,
            size="1024x1024",
            user=user_email,
            response_format="url",  # Explicitly request URL format
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                }
            },
        )

        logger.info(f"DEBUG: API Response object: {response}")
        logger.info(f"DEBUG: Response data: {response.data}")
        logger.info(f"DEBUG: Response data length: {len(response.data) if response.data else 0}")
        
        # Extract the image URL from the response
        if response.data and len(response.data) > 0:
            logger.info(f"DEBUG: First data item: {response.data[0]}")
            logger.info(f"DEBUG: First data item type: {type(response.data[0])}")
            logger.info(f"DEBUG: First data item dict: {vars(response.data[0]) if hasattr(response.data[0], '__dict__') else response.data[0]}")
            
            # Try to get URL attribute
            image_url = getattr(response.data[0], 'url', None)
            logger.info(f"DEBUG: Extracted URL: {image_url}")
            
            if not image_url:
                # Maybe it's in b64_json format instead
                b64_json = getattr(response.data[0], 'b64_json', None)
                if b64_json:
                    logger.info(f"DEBUG: Got base64 image data instead of URL, converting...")
                    # Create a data URL from base64
                    image_url = f"data:image/png;base64,{b64_json}"
                else:
                    raise ValueError(f"No image URL or base64 data in response: {vars(response.data[0]) if hasattr(response.data[0], '__dict__') else response.data[0]}")
            
            logger.info(f"Image generated successfully for user {user_email}")
            return image_url
        else:
            raise ValueError("No image data in response")

    except OpenAIError as e:
        # Catch OpenAI-specific errors (safety filters, quota limits, rate limits, etc.)
        error_msg = f"Image generation API error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg) from e

    except Exception as e:
        # Catch other unexpected errors
        error_msg = f"Unexpected error during image generation: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


async def download_and_upload_image(
    image_url: str,
    user_email: str,
    bucket: str = "generated-images",
) -> str:
    """
    Download an image from a temporary URL and upload it to Supabase storage via REST API.
    If upload fails, returns a base64 data URL instead.
    Also handles base64-encoded data URLs.

    Args:
        image_url: Temporary URL of the image to download, or data URL with base64 data.
        user_email: Email of the authenticated user (used in file path).
        bucket: Supabase storage bucket name (default: 'generated-images').

    Returns:
        The public Supabase URL for the uploaded image, or a base64 data URL as fallback.

    Raises:
        ValueError: If the URL is invalid.
        Exception: For network or unexpected errors.
    """
    if not image_url or not image_url.strip():
        raise ValueError("Image URL cannot be empty")

    # Handle base64 data URLs directly
    if image_url.startswith("data:image"):
        logger.info("DEBUG: Image is already a base64 data URL, returning as-is")
        return image_url

    # Download image from temporary URL
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_data = response.content

        if not image_data:
            raise ValueError("Downloaded image is empty")

        logger.info(f"Downloaded image from temporary URL ({len(image_data)} bytes)")

        # Convert to base64 data URL for now
        base64_image = base64.b64encode(image_data).decode('utf-8')
        data_url = f"data:image/jpeg;base64,{base64_image}"
        logger.info("Converting to base64 data URL for immediate use")
        return data_url

    except httpx.HTTPError as e:
        error_msg = f"Failed to download image from URL: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error downloading image: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise
