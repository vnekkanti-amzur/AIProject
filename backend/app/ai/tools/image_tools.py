"""Tools for image generation in the chat agent."""

from langchain_core.tools import tool

from app.services.image_service import generate_chat_image, download_and_upload_image


def create_image_generator_tool(user_email: str):
    """Factory to create an image generator tool with user_email bound.
    
    Args:
        user_email: Email of the authenticated user (for tracking and file paths).
    
    Returns:
        A LangChain tool that generates images.
    """
    
    @tool
    async def image_generator(prompt: str) -> str:
        """
        Generate an image from a text description and upload it to Supabase storage.

        This tool should be called when the user wants to create, draw, generate, or visualize something.

        Args:
            prompt: Detailed text description of the image to generate.

        Returns:
            Markdown image syntax with the Supabase public URL.
            Format: ![generated image](https://...)

        Raises:
            Exception: If image generation, download, or upload fails.
        """
        try:
            # Step 1: Generate image via LiteLLM
            temp_url = await generate_chat_image(prompt, user_email)

            # Step 2: Download from temporary URL and upload to Supabase
            permanent_url = await download_and_upload_image(temp_url, user_email)

            # Step 3: Return as Markdown image syntax
            return f"![generated image]({permanent_url})"

        except ValueError as e:
            raise ValueError(f"Image generation failed: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Error generating and uploading image: {type(e).__name__}: {str(e)}") from e
    
    return image_generator


__all__ = ["create_image_generator_tool"]
