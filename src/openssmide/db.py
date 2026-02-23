import os
from datetime import datetime

from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "ss_ai"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

sessions = db.sessions
messages = db.messages


def create_session(title: str):
    doc = {
        "title": title,
        "created_at": datetime.utcnow(),
        "last_active": datetime.utcnow(),
    }
    return sessions.insert_one(doc).inserted_id


def add_message(session_id, role: str, text: str, image_path: str | None = None):
    messages.insert_one(
        {
            "session_id": session_id,
            "role": role,
            "text": text,
            "image_path": image_path,
            "timestamp": datetime.utcnow(),
        }
    )
    sessions.update_one(
        {"_id": session_id},
        {"$set": {"last_active": datetime.utcnow()}},
    )


def list_sessions(limit: int = 10):
    return list(sessions.find().sort("last_active", -1).limit(limit))


def get_session_messages(session_id):
    return list(messages.find({"session_id": session_id}).sort("timestamp", 1))
