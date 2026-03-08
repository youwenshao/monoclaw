import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.onboarding_state import ChatMessage, ChatResponse
from backend.services.complexity import infer_complexity
from backend.services.interaction import InteractionMode, interaction_manager
from backend.services.llm import CloudAPIError, llm_service
from backend.services.tool_router import tool_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

conversations: dict[str, list[dict[str, str]]] = {}

SYSTEM_PROMPT = (
    "You are Mona, a helpful AI assistant running locally on the user's Mac. "
    "You have access to 12 industry-specific tool suites and can route requests "
    "to the right tool automatically. Be warm, concise, and proactive."
)


def _build_system_prompt(tool_id: str | None, message: str) -> str:
    """Build system prompt with optional tool-suite context."""
    match = tool_router.route(message, tool_id)
    if match:
        return f"{SYSTEM_PROMPT}\n\n{match.system_context}"
    return SYSTEM_PROMPT


def _clean_message(message: str) -> str:
    """Strip slash commands from the user-facing message."""
    return tool_router.strip_slash_command(message)


@router.get("/tools")
async def list_tools():
    """Return all available tool suites for the UI dropdown."""
    return tool_router.get_all_tools()


@router.post("/message", response_model=ChatResponse)
async def send_message(msg: ChatMessage):
    conversation_id = msg.conversation_id or str(uuid.uuid4())

    if conversation_id not in conversations:
        conversations[conversation_id] = []

    clean_msg = _clean_message(msg.message)
    system_prompt = _build_system_prompt(msg.tool_id, msg.message)

    conversations[conversation_id].append({"role": "user", "content": clean_msg})

    history = conversations[conversation_id]
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])

    complexity = infer_complexity(clean_msg) if msg.model_id is None else None

    try:
        response_text = await llm_service.generate(
            prompt=context,
            system_prompt=system_prompt,
            model_id=msg.model_id,
            complexity=complexity,
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

    clean_msg = _clean_message(msg.message)
    system_prompt = _build_system_prompt(msg.tool_id, msg.message)

    conversations[conversation_id].append({"role": "user", "content": clean_msg})

    history = conversations[conversation_id]
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])

    complexity = infer_complexity(clean_msg) if msg.model_id is None else None

    async def event_stream():
        full_response = []
        try:
            async for token in llm_service.generate_stream(
                prompt=context,
                system_prompt=system_prompt,
                model_id=msg.model_id,
                complexity=complexity,
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
    task_type = req.get("task_type", "default")
    conversation_id = str(uuid.uuid4())

    prompt_text = (
        "Let's try your first task together! I'll guide you step by step. "
        "What would you like to work on?"
    )

    conversations[conversation_id] = [
        {"role": "assistant", "content": prompt_text},
    ]

    return ChatResponse(response=prompt_text, conversation_id=conversation_id)
