"""AWS Lambda entry point (used once the API is deployed)."""

from mangum import Mangum

from .main import app

handler = Mangum(app)
