import os

from motor.motor_asyncio import AsyncIOMotorClient as _mongo_client_
from pymongo import MongoClient

import config

from ..logging import LOGGER


# ---------------------------------------------------------
# Get MongoDB URI
# ---------------------------------------------------------

MONGO_URI = (
    getattr(config, "MONGO_DB_URI", None)
    or os.getenv("MONGO_DB_URI")
    or ""
).strip()


# ---------------------------------------------------------
# Validate MongoDB URI
# ---------------------------------------------------------

if not MONGO_URI:
    LOGGER(__name__).error(
        "MONGO_DB_URI is missing or empty. "
        "Please add MONGO_DB_URI to Heroku Config Vars."
    )

    raise RuntimeError(
        "MONGO_DB_URI is missing or empty."
    )


# ---------------------------------------------------------
# Connect to MongoDB
# ---------------------------------------------------------

try:

    _mongo_async_ = _mongo_client_(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
    )

    _mongo_sync_ = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
    )

    # Database name
    mongodb = _mongo_async_.Anon
    pymongodb = _mongo_sync_.Anon

    LOGGER(__name__).info(
        "MongoDB client initialized successfully."
    )

except Exception as e:

    LOGGER(__name__).error(
        f"MongoDB connection initialization failed: {e}"
    )

    raise
