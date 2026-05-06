from typing import Dict, Any, List
import json
import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from ..config import settings
from . import tools
from ..classifier import log_llm_usage

logger = structlog.get_logger()

# OpenAI client setup removed (switched to Claude)

SYSTEM_PROMPT = """You are JARVIS, an AI bookkeeping assistant for Zalazar Holdings LLC.
You answer questions about the company's financial data using the provided tools.
You query the database via tools, never generating raw SQL.

Guardrails:
- Always report the as-of date of the P&L view.
- If you had to disambiguate (e.g., which property the user meant), mention it in the response.
- If a question is ambiguous (e.g., "what did I spend last month?"), ask which property or confirm "portfolio-wide" first. Do not guess.
- Every answer must end with a source footer like: "Based on transactions through {latest_reviewed_date}. {N} transactions currently in review — they're not in this total."
"""

TOOL_DEFINITIONS = [
    {
        "name": "query_pnl",
        "description": "Monthly P&L for a property or portfolio across a date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property ID, or null for portfolio-wide"},
                "entity_id": {"type": "string"},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "required": ["entity_id", "start_date", "end_date"]
        }
    },
    {
        "name": "query_transactions",
        "description": "List individual transactions matching filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property ID, or null for portfolio-wide"},
                "entity_id": {"type": "string"},
                "account_code": {"type": "string", "description": "Account code, or null"},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "min_amount": {"type": "number", "description": "Minimum amount, or null"},
                "limit": {"type": "integer"}
            },
            "required": ["entity_id", "start_date", "end_date"]
        }
    },
    {
        "name": "list_properties",
        "description": "List all active properties for an entity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"}
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "list_accounts",
        "description": "List the chart of accounts (leaf accounts only).",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "review_queue_count",
        "description": "Return the count of transactions currently in review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"}
            },
            "required": ["entity_id"]
        }
    }
]

async def ask_jarvis(session: AsyncSession, entity_id: str, question: str, conversation_history: List[Dict[str, str]] = None) -> str:
    if not settings.ANTHROPIC_API_KEY:
        return "Anthropic API key not configured. I cannot process this request."
        
    messages = []
    if conversation_history:
        # Filter messages to only include supported roles for Claude (user, assistant)
        for msg in conversation_history:
            if msg["role"] in ["user", "assistant"]:
                messages.append(msg)
                
    messages.append({"role": "user", "content": question})
    
    system_prompt = SYSTEM_PROMPT + f"\n\nThe user is asking about entity_id: {entity_id}. Use this entity_id in all tool calls."

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY.get_secret_value())
    
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
        tools=TOOL_DEFINITIONS,
        temperature=0
    )
    
    # Log usage (M4.4)
    try:
        usage = response.usage
        await log_llm_usage(
            session, 
            provider="anthropic", 
            model="claude-sonnet-4-6", 
            prompt_tokens=usage.input_tokens, 
            completion_tokens=usage.output_tokens, 
            total_tokens=usage.input_tokens + usage.output_tokens, 
            context_type="jarvis_initial",
            entity_id=entity_id
        )
    except Exception as e:
        logger.error("Failed to log initial JARVIS usage", error=str(e))  
    
    # Handle tool calls
    if response.stop_reason == "tool_use":
        # Add assistant message with tool calls to history
        messages.append({"role": "assistant", "content": response.content})
        
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                func_name = content_block.name
                args = content_block.input
                tool_use_id = content_block.id
                
                logger.info("JARVIS executing tool", tool=func_name, args=args)
                
                tool_result = ""
                try:
                    if func_name == "query_pnl":
                        res = await tools.query_pnl(session, **args)
                        tool_result = json.dumps(res, default=str)
                    elif func_name == "query_transactions":
                        res = await tools.query_transactions(session, **args)
                        tool_result = json.dumps(res, default=str)
                    elif func_name == "list_properties":
                        res = await tools.list_properties(session, **args)
                        tool_result = json.dumps(res, default=str)
                    elif func_name == "list_accounts":
                        res = await tools.list_accounts(session)
                        tool_result = json.dumps(res, default=str)
                    elif func_name == "review_queue_count":
                        res = await tools.review_queue_count(session, **args)
                        tool_result = str(res)
                except Exception as e:
                    logger.error("JARVIS tool error", error=str(e))
                    tool_result = f"Error executing tool: {str(e)}"
                
                tool_results.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": tool_result,
                        }
                    ],
                })
        
        messages.extend(tool_results)
            
        # Get final response
        final_response_msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            temperature=0
        )
        
        # Log usage (M4.4)
        try:
            usage = final_response_msg.usage
            await log_llm_usage(
                session, 
                provider="anthropic", 
                model="claude-sonnet-4-6", 
                prompt_tokens=usage.input_tokens, 
                completion_tokens=usage.output_tokens, 
                total_tokens=usage.input_tokens + usage.output_tokens, 
                context_type="jarvis_final",
                entity_id=entity_id
            )
        except Exception as e:
            logger.error("Failed to log final JARVIS usage", error=str(e))
            
        content = final_response_msg.content[0].text
    else:
        content = response.content[0].text

    # Enforce Source Footer (M10.1)
    try:
        # Get latest reviewed date
        res = await session.execute(text("""
            SELECT MAX(transaction_date) 
            FROM transactions 
            WHERE entity_id = :eid AND status IN ('reviewed', 'auto_categorized')
        """), {"eid": entity_id})
        latest_date = res.scalar() or "N/A"
        
        # Get queue count
        res = await session.execute(text("""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE entity_id = :eid AND status IN ('pending_review', 'ai_suggested', 'flagged')
        """), {"eid": entity_id})
        queue_count = res.scalar() or 0
        
        footer = f"\n\n---\n*Based on transactions through {latest_date}. {queue_count} transactions currently in review — they're not in this total.*"
        if footer not in content:
            content += footer
    except Exception as e:
        logger.error("Failed to append footer", error=str(e))

    return content
