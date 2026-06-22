"""spots — spot domain (12 features). See feature spec §4.3.

Owns: spots, spot_details, spot_images, spot_moods, collections, moods seed.
"""

from app.modules.spots.routes import router

__all__ = ["router"]
