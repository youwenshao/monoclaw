"""WeChat Work (Enterprise WeChat) messaging handler."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("openclaw.supplier-bot.wechat-work")


class WeChatWorkHandler:
    """Handles WeChat Work (企业微信) API for internal / B2B communication."""

    def __init__(self, corp_id: str, agent_id: str, secret: str) -> None:
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.secret = secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def send_message(self, to_user: str, content: str) -> dict[str, Any]:
        """Send a text message via WeChat Work.

        In production this POSTs to
        ``https://qyapi.weixin.qq.com/cgi-bin/message/send``.
        """
        token = self._get_access_token()
        logger.info(
            "WeChatWork send → to=%s agent=%s len=%d token=%s…",
            to_user,
            self.agent_id,
            len(content),
            token[:8] if token else "none",
        )
        return {
            "status": "sent_stub",
            "to_user": to_user,
            "agent_id": self.agent_id,
            "content_length": len(content),
            "timestamp": time.time(),
        }

    def receive_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse an incoming WeChat Work callback payload.

        Expected keys:
          - MsgType (text | image | voice | event)
          - FromUserName
          - Content / MediaId
          - CreateTime
          - AgentID
        """
        msg_type = payload.get("MsgType", "text")
        from_user = payload.get("FromUserName", "")
        content = payload.get("Content", "")
        create_time = payload.get("CreateTime", int(time.time()))
        agent_id = payload.get("AgentID", self.agent_id)

        parsed: dict[str, Any] = {
            "msg_type": msg_type,
            "from_user": from_user,
            "create_time": create_time,
            "agent_id": agent_id,
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

        logger.info("WeChatWork receive ← from=%s type=%s agent=%s", from_user, msg_type, agent_id)
        return parsed

    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """Return a cached access token, refreshing if expired.

        Stub — in production calls
        ``https://qyapi.weixin.qq.com/cgi-bin/gettoken``.
        """
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        logger.info("Refreshing WeChatWork token for corp_id=%s…", self.corp_id)
        self._access_token = f"work_stub_{self.corp_id}_{int(now)}"
        self._token_expires_at = now + 7200
        return self._access_token
