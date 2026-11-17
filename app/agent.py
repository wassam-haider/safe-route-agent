import logging
from typing import Union

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage

from app.config import settings, validate_settings
from app.middleware import build_middleware
from app.results import finalize, map_payload, render_text
from app.schemas import AskUser, RouteRecommendation
from app.tools import ALL_TOOLS

logger = logging.getLogger("saferoute")

_agent = None
SESSIONS: dict[str, list] = {}
MAX_HISTORY = 12


def get_agent():
    global _agent
    if _agent is None:
        validate_settings()
        model = init_chat_model(
            settings.openrouter_model,
            model_provider="openrouter",
            temperature=0,
        )
        _agent = create_agent(
            model=model,
            tools=ALL_TOOLS,
            middleware=build_middleware(),
            response_format=ToolStrategy(Union[AskUser, RouteRecommendation]),
            name="saferoute_agent",
        )
    return _agent


def reset_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)


def run_turn(session_id: str, user_text: str) -> dict:
    agent = get_agent()
    history = SESSIONS.setdefault(session_id, [])
    messages = history + [HumanMessage(content=user_text)]

    try:
        result = agent.invoke({"messages": messages}, config={"recursion_limit": 60})
    except Exception as exc:
        logger.exception("agent failed")
        raise RuntimeError(f"Agent failed: {exc}") from exc

    out = result.get("structured_response")
    if isinstance(out, AskUser):
        reply = {"type": "question", "message": out.question}
    elif isinstance(out, RouteRecommendation):
        out = finalize(out)
        reply = {
            "type": "route",
            "message": render_text(out),
            "recommendation": out.model_dump(),
            "map": map_payload(out),
        }
    else:
        last = result["messages"][-1].content if result.get("messages") else ""
        text = last if isinstance(last, str) and last else "I could not finish that request. Please try again."
        reply = {"type": "text", "message": text}

    history.append(HumanMessage(content=user_text))
    history.append(AIMessage(content=reply["message"]))
    del history[:-MAX_HISTORY]
    return reply