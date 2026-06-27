# Inngest package
from app.inngest.client import inngest_client
from app.inngest.process_image import process_jewelry_image

# All functions to register with Inngest serve()
inngest_functions = [process_jewelry_image]

__all__ = ["inngest_client", "inngest_functions"]
