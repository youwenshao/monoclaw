"""WeChat Official Account messaging handler."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("openclaw.supplier-bot.wechat")


class WeChatHandler:
    """Handles WeChat Official Account API interactions for supplier messaging."""

    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def send_message(self, to_user: str, content: str) -> dict[str, Any]:
        """Send a text message to a WeChat user.

        In production this would POST to the WeChat API.  Currently logs and
        returns a stub acknowledgement so the rest of the pipeline can run
        without live credentials.
        """
        token = self.get_access_token()
        logger.info(
            "WeChat send_message → to=%s len=%d token=%s…",
            to_user,
            len(content),
            token[:8] if token else "none",
        )
        return {
            "status": "sent_stub",
            "to_user": to_user,
            "content_length": len(content),
            "timestamp": time.time(),
        }

    def receive_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse an incoming WeChat message webhook payload.

        Expected keys in *payload*:
          - MsgType (text | image | voice | event)
          - FromUserName
          - Content (for text messages)
          - CreateTime
        """
        msg_type = payload.get("MsgType", "text")
        from_user = payload.get("FromUserName", "")
        content = payload.get("Content", "")
        create_time = payload.get("CreateTime", int(time.time()))

        parsed: dict[str, Any] = {
            "msg_type": msg_type,
            "from_user": from_user,
            "create_time": create_time,
        }

        if msg_type == "text":
            parsed["content"] = content
        elif msg_type == "image":
            parsed["pic_url"] = payload.get("PicUrl", "")
            parsed["media_id"] = payload.get("MediaId", "")
        elif msg_type == "voice":
            parsed["media_id"] = payload.get("MediaId", "")
            parsed["recognition"] = payload.get("Recognition", "")
        elif msg_type == "event":
            parsed["event"] = payload.get("Event", "")
            parsed["event_key"] = payload.get("EventKey", "")

        logger.info("WeChat receive_message ← from=%s type=%s", from_user, msg_type)
        return parsed

    def get_access_token(self) -> str:
        """Return a cached access token, refreshing if expired.

        Stub implementation — in production this calls
        ``https://api.weixin.qq.com/cgi-bin/token``.
        """
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        logger.info("Refreshing WeChat access token for app_id=%s…", self.app_id)
        self._access_token = f"stub_token_{self.app_id}_{int(now)}"
        self._token_expires_at = now + 7200  # 2-hour TTL like real tokens
        return self._access_token
