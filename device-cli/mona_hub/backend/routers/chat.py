import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.onboarding_state import ChatMessage, ChatResponse
from backend.services.interaction import InteractionMode, interaction_manager
from backend.services.llm import CloudAPIError, llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

conversations: dict[str, list[dict[str, str]]] = {}

GUIDED_TASK_PROMPTS: dict[str, dict[str, str]] = {
    "default": {
        "default": (
            "Let's try your first task together! I'll guide you step by step. "
            "What would you like to work on?"
        ),
    },
}

SYSTEM_PROMPT = "You are Mona, a helpful onboarding assistant for a new Mac setup."


@router.post("/message", response_model=ChatResponse)
async def send_message(msg: ChatMessage):
    conversation_id = msg.conversation_id or str(uuid.uuid4())

    if conversation_id not in conversations:
        conversations[conversation_id] = []

    conversations[conversation_id].append({"role": "user", "content": msg.message})

    history = conversations[conversation_id]
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])

    try:
        response_text = await llm_service.generate(
            prompt=context,
            system_prompt=SYSTEM_PROMPT,
            model_id=msg.model_id,
        )
    except CloudAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected LLM error: %s", exc)
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}") from exc

    conversations[conversation_id].append({"role": "assistant", "content": response_text})

    return ChatResponse(response=response_text, conversation_id=conversation_id)


@router.post("/message/stream")
async def send_message_stream(msg: ChatMessage):
    acquired = await interaction_manager.acquire(InteractionMode.TEXT_GENERATING)
    if not acquired:
        raise HTTPException(status_code=409, detail="Another interaction is in progress")

    conversation_id = msg.conversation_id or str(uuid.uuid4())

    if conversation_id not in conversations:
        conversations[conversation_id] = []

    conversations[conversation_id].append({"role": "user", "content": msg.message})

    history = conversations[conversation_id]
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])

    async def event_stream():
        full_response = []
        try:
            async for token in llm_service.generate_stream(
                prompt=context,
                system_prompt=SYSTEM_PROMPT,
                model_id=msg.model_id,
            ):
                full_response.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
            conversations[conversation_id].append(
                {"role": "assistant", "content": "".join(full_response)}
            )
            yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id})}\n\n"
        except CloudAPIError as exc:
            logger.warning("Cloud API error during stream: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        except Exception as exc:
            logger.error("Unexpected error during stream: %s", exc)
            yield f"data: {json.dumps({'error': f'An unexpected error occurred: {exc}'})}\n\n"
        finally:
            await interaction_manager.release()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/message/abort")
async def abort_message():
    llm_service.abort_generation()
    await interaction_manager.release()
    return {"status": "aborted"}


@router.post("/guided-task", response_model=ChatResponse)
async def guided_task(req: dict):
    industry = req.get("industry", "default")
    task_type = req.get("task_type", "default")
    conversation_id = str(uuid.uuid4())

    industry_prompts = GUIDED_TASK_PROMPTS.get(industry, GUIDED_TASK_PROMPTS["default"])
    prompt_text = industry_prompts.get(task_type, industry_prompts.get("default", ""))

    if not prompt_text:
        prompt_text = GUIDED_TASK_PROMPTS["default"]["default"]

    conversations[conversation_id] = [
        {"role": "assistant", "content": prompt_text},
    ]

    return ChatResponse(response=prompt_text, conversation_id=conversation_id)
