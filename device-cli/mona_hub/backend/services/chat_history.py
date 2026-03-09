import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CHAT_HISTORY_DIR = Path("/opt/openclaw/state/chat")


class ChatHistoryService:
    def __init__(self, storage_dir: Path = CHAT_HISTORY_DIR):
        self.storage_dir = storage_dir
        self._ensure_dir()

    def _ensure_dir(self):
        if not self.storage_dir.exists():
            try:
                self.storage_dir.mkdir(parents=True, exist_ok=True)
                # Try to set permissions if running as root
                if os.getuid() == 0:
                    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "admin"
                    import subprocess
                    subprocess.run(["chown", "-R", f"{user}:", str(self.storage_dir)], check=False)
            except Exception as e:
                logger.error(f"Failed to create chat storage directory {self.storage_dir}: {e}")

    def _get_file_path(self, conversation_id: str) -> Path:
        return self.storage_dir / f"{conversation_id}.json"

    def list_conversations(self) -> List[Dict[str, Any]]:
        conversations = []
        if not self.storage_dir.exists():
            return conversations

        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    conversations.append({
                        "id": data.get("id"),
                        "title": data.get("title") or "New Chat",
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "last_accessed_at": data.get("last_accessed_at"),
                        "message_count": len(data.get("messages", [])),
                    })
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read conversation file {file_path}: {e}")
        
        # Sort by updated_at descending
        conversations.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return conversations

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_file_path(conversation_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            
            # Update last_accessed_at
            data["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
            self._save_conversation(data)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read conversation {conversation_id}: {e}")
            return None

    def create_conversation(self, title: Optional[str] = None) -> Dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "id": conversation_id,
            "title": title or "New Chat",
            "created_at": now,
            "updated_at": now,
            "last_accessed_at": now,
            "messages": []
        }
        self._save_conversation(data)
        return data

    def append_messages(self, conversation_id: str, messages: List[Dict[str, str]], title: Optional[str] = None) -> bool:
        data = self.get_conversation(conversation_id)
        if not data:
            # Create if not exists
            data = self.create_conversation(title=title)
            conversation_id = data["id"]

        data["messages"].extend(messages)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data["last_accessed_at"] = data["updated_at"]
        
        if title:
            data["title"] = title
        elif not data.get("title") or data.get("title") == "New Chat":
            # Auto-generate title from first user message
            for msg in data["messages"]:
                if msg["role"] == "user":
                    content = msg["content"]
                    data["title"] = (content[:40] + "...") if len(content) > 40 else content
                    break

        return self._save_conversation(data)

    def delete_conversation(self, conversation_id: str) -> bool:
        file_path = self._get_file_path(conversation_id)
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except OSError as e:
                logger.error(f"Failed to delete conversation {conversation_id}: {e}")
                return False
        return False

    def _save_conversation(self, data: Dict[str, Any]) -> bool:
        conversation_id = data["id"]
        file_path = self._get_file_path(conversation_id)
        temp_path = file_path.with_suffix(".tmp")
        
        try:
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(file_path)
            
            # Ensure permissions
            if os.getuid() == 0:
                user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "admin"
                import subprocess
                subprocess.run(["chown", f"{user}:", str(file_path)], check=False)
            
            return True
        except OSError as e:
            logger.error(f"Failed to save conversation {conversation_id}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    def drain_older_than(self, days: int = 30):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = 0
        if not self.storage_dir.exists():
            return 0

        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    last_accessed = data.get("last_accessed_at")
                    if last_accessed:
                        dt = datetime.fromisoformat(last_accessed)
                        if dt < cutoff:
                            file_path.unlink()
                            count += 1
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.warning(f"Failed to process {file_path} for drain: {e}")
        
        if count > 0:
            logger.info(f"Drained {count} conversations older than {days} days")
        return count


chat_history_service = ChatHistoryService()
