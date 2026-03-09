import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.onboarding_state import ChatMessage, ChatResponse
from backend.services.chat_history import chat_history_service
from backend.services.interaction import InteractionMode, interaction_manager
from backend.services.llm import CloudAPIError, llm_service
from backend.services.tool_router import tool_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


SYSTEM_PROMPT = (
    "You are Mona, a helpful AI assistant running locally on the user's Mac "
    "via the OpenClaw agent infrastructure. You have access to industry-specific "
    "tool suites loaded as OpenClaw skills and can execute tools through the gateway. "
    "Be warm, concise, and proactive."
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


@router.get("/conversations")
async def list_conversations():
    """List all chat conversations."""
    return chat_history_service.list_conversations()


@router.get("/conversations/{id}")
async def get_conversation(id: str):
    """Get full chat history for a conversation."""
    conv = chat_history_service.get_conversation(id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/conversations")
async def create_conversation(body: dict = None):
    """Create a new chat conversation."""
    title = body.get("title") if body else None
    return chat_history_service.create_conversation(title=title)


@router.delete("/conversations/{id}")
async def delete_conversation(id: str):
    """Delete a chat conversation."""
    success = chat_history_service.delete_conversation(id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}


@router.post("/message", response_model=ChatResponse)
async def send_message(msg: ChatMessage):
    conversation_id = msg.conversation_id or str(uuid.uuid4())
    
    # Ensure conversation exists in persistent storage
    if not chat_history_service.get_conversation(conversation_id):
        chat_history_service.create_conversation(title=None)

    clean_msg = _clean_message(msg.message)
    system_prompt = _build_system_prompt(msg.tool_id, msg.message)

    # Get history from persistent storage
    conv = chat_history_service.get_conversation(conversation_id)
    history = conv.get("messages", [])
    
    # Format for LLM
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])
    if context:
        context += f"\nuser: {clean_msg}"
    else:
        context = f"user: {clean_msg}"

    try:
        response_text = await llm_service.generate(
            prompt=context,
            system_prompt=system_prompt,
        )
    except CloudAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected LLM error: %s", exc)
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}") from exc

    # Persist to JSON file
    chat_history_service.append_messages(conversation_id, [
        {"role": "user", "content": clean_msg},
        {"role": "assistant", "content": response_text}
    ])

    return ChatResponse(response=response_text, conversation_id=conversation_id)


@router.post("/message/stream")
async def send_message_stream(msg: ChatMessage):
    acquired = await interaction_manager.acquire(InteractionMode.TEXT_GENERATING)
    if not acquired:
        raise HTTPException(status_code=409, detail="Another interaction is in progress")

    conversation_id = msg.conversation_id or str(uuid.uuid4())
    
    # Ensure conversation exists in persistent storage
    if not chat_history_service.get_conversation(conversation_id):
        chat_history_service.create_conversation(title=None)

    clean_msg = _clean_message(msg.message)
    system_prompt = _build_system_prompt(msg.tool_id, msg.message)

    # Get history from persistent storage
    conv = chat_history_service.get_conversation(conversation_id)
    history = conv.get("messages", [])
    
    # Format for LLM
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])
    if context:
        context += f"\nuser: {clean_msg}"
    else:
        context = f"user: {clean_msg}"

    async def event_stream():
        full_response = []
        try:
            async for token in llm_service.generate_stream(
                prompt=context,
                system_prompt=system_prompt,
            ):
                full_response.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
            
            # Persist to JSON file after stream completes
            chat_history_service.append_messages(conversation_id, [
                {"role": "user", "content": clean_msg},
                {"role": "assistant", "content": "".join(full_response)}
            ])
            
            yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id})}\n\n"
        except CloudAPIError as exc:
            logger.warning("Gateway error during stream: %s", exc)
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
    
    prompt_text = (
        "Let's try your first task together! I'll guide you step by step. "
        "What would you like to work on?"
    )
    
    # Create conversation and persist initial message
    conv = chat_history_service.create_conversation(title="First Task")
    conversation_id = conv["id"]
    chat_history_service.append_messages(conversation_id, [
        {"role": "assistant", "content": prompt_text}
    ])

    return ChatResponse(response=prompt_text, conversation_id=conversation_id)
