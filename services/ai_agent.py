import config
import logging
from typing import TypedDict
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class AgentResponse(BaseModel):
    reply_to_user: str = Field(
        description="The AI's friendly, conversational, and helpful reply to the user. Keep it concise."
    )
    is_important: bool = Field(
        description="True if the user's message is important, urgent, requires an admin, reports a bug, asks for human help, or is a NEW feature request. False for casual chat or questions the AI has easily answered."
    )

class GraphState(TypedDict):
    user_message: str
    reply: str
    is_important: bool

def process_message(state: GraphState):
    if not config.MISTRAL_API_KEY:
        logger.warning("MISTRAL_API_KEY is not set.")
        return {"reply": "Sorry, AI features are not configured at the moment.", "is_important": True}

    llm = ChatMistralAI(
        model="mistral-medium-2508", # Recommended for best reasoning capabilities
        mistral_api_key=config.MISTRAL_API_KEY,
        temperature=0.2, # Lower temperature for more consistent classification
    )
    
    structured_llm = llm.with_structured_output(AgentResponse)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are an expert AI assistant for a Telegram bot.\n\n"
         "### INSTRUCTIONS\n"
         "Analyze the user's message and determine if it needs to be forwarded to a human admin.\n\n"
         "1. SET 'is_important' = true AND tell the user you are forwarding their message to the admin if:\n"
         "   - It is a bug report, billing issue, or complex query.\n"
         "   - The user is explicitly asking for human help.\n"
         "   - The user is requesting a NEW feature that is NOT in the 'Existing Features' list below.\n\n"
         "2. SET 'is_important' = false AND simply answer them directly if:\n"
         "   - It is general chit-chat (e.g., 'hello', 'how are you', 'thanks').\n"
         "   - They are asking a question about the 'Existing Features' currently supported.\n\n"
         "### EXISTING FEATURES LIST\n"
         "- Multiple Database Support (Supports multiple databases, On / Off control)\n"
         "- Premium System (Premium plan feature, Refer & earn premium, Premium + Refer toggle)\n"
         "- AI Spell Check (Auto spell correction using AI)\n"
         "- Force Subscribe System (Custom force subscribe, Request-to-join support, Auto file send after join)\n"
         "- Rename System (File rename feature, On / Off option)\n"
         "- Stream System (Stream feature On / Off, Custom stream, Stream with multiple player support)\n"
         "- URL Shortener (URL shortener feature On / Off, Custom URL shortener support)\n"
         "- PM Search (Private message search, Enable / Disable)\n"
         "- Advanced File Options (Choose Language, Select Season, Select Episode, Choose Quality, Filter by Year)\n"
         "- Auto Approve (Auto approve join requests, On / Off control)\n"
         "- Token Verification (Token verification system, On / Off toggle)\n"
         "- Send All Button (Broadcast files with a single button)\n"
         "- Custom Buttons (Custom tutorial button, Fully configurable)\n"
         "- Auto File Delete (Bot PM file auto delete system)\n\n"
         "### YOUR TONE\n"
         "Always be polite, helpful, and highly contextual. Do not hallucinate features not on the list."
        ),
        ("user", "{user_message}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = chain.invoke({"user_message": state["user_message"]})
        return {
            "reply": result.reply_to_user,
            "is_important": result.is_important
        }
    except Exception as e:
        logger.error(f"Error in LLM invocation: {e}")
        return {
            "reply": "I'm having a bit of trouble processing that. I've sent it to the admin just in case.",
            "is_important": True
        }

def build_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("process", process_message)
    workflow.add_edge(START, "process")
    workflow.add_edge("process", END)
    return workflow.compile()

agent_app = build_graph()

async def analyze_message_with_ai(text: str) -> dict:
    """Analyze a user message with the LLM Agent."""
    if not text:
        return {"reply": "I couldn't read your message.", "is_important": True}
        
    result = await agent_app.ainvoke({"user_message": text})
    return result
