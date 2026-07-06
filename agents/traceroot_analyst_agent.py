"""
TracerootAnalystAgent — The SQL Gateway Interface
===================================================
A specialized agent that converts natural language into ClickHouse SQL
to query Traceroot's SQL Query Gateway API.
"""

import logging
import json
import httpx
from typing import Dict, Any, List

from google import genai
from server.tracing import observe, update_current_span

from agents.base_agent import BaseAgent

# Traceroot's curated SQL schema for the new SQL Query Gateway
TRACEROOT_SCHEMA = """
TABLE traces (
    trace_id String,
    name String,
    start_time DateTime64(3),
    end_time DateTime64(3),
    duration_ms Float64,
    status String,
    user_id String,
    session_id String
)

TABLE spans (
    span_id String,
    trace_id String,
    parent_span_id String,
    name String,
    kind String,
    start_time DateTime64(3),
    end_time DateTime64(3),
    duration_ms Float64,
    status String
)
"""

class TracerootAnalystAgent(BaseAgent):
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("traceroot_api_key", config.get("TRACEROOT_API_KEY", ""))
        self.base_url = "https://api.traceroot.ai/v1/sql"  # The new SQL Gateway API
        self.logger = logging.getLogger("mizune.agents.traceroot_analyst")
        
        # Initialize Gemini for Text-to-SQL
        self.gemini_key = config.get("gemini_api_key", config.get("GEMINI_API_KEY", "FAKE_KEY"))
        self.client = genai.Client(api_key=self.gemini_key)

    @observe(name="traceroot_analyst.execute", type="agent")
    async def execute(self, query: str, context: dict = None) -> str:
        """
        Takes a natural language question, generates SQL, queries Traceroot, and returns JSON string results.
        Satisfies BaseAgent.execute signature.
        """
        # Adapt string query to dict if we need to call run directly
        return json.dumps(await self.run({"question": query}))
        
    @observe(name="traceroot_analyst.run", type="agent")
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a natural language question, generates SQL, queries Traceroot, and returns results.
        """
        question = input_data.get("question", "")
        update_current_span(metadata={"analyst.question": question})
        
        try:
            # 1. Generate SQL
            sql = await self._generate_sql(question)
            update_current_span(metadata={"analyst.sql": sql})
            
            # 2. Execute SQL against Traceroot SQL Gateway
            results = await self._execute_sql(sql)
            update_current_span(metadata={"analyst.row_count": len(results.get("rows", []))})
            
            # 3. Summarize the answer
            summary = await self._summarize_results(question, results)
            
            return {
                "status": "success",
                "sql": sql,
                "data": results,
                "summary": summary
            }
        except Exception as e:
            self.logger.error(f"Error in TracerootAnalystAgent: {e}")
            return {"status": "error", "error": str(e)}

    @observe(name="traceroot_analyst.generate_sql", type="llm")
    async def _generate_sql(self, question: str) -> str:
        prompt = f"""
You are an expert ClickHouse SQL analyst for Traceroot.
Translate the user's natural language question into a valid ClickHouse SQL query based on this schema:

{TRACEROOT_SCHEMA}

Rules:
1. Output ONLY the raw SQL query. No markdown, no explanation.
2. Use safe SQL practices (e.g. LIMIT 100).

User Question: {question}
"""
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            sql = response.text.strip()
        except Exception as e:
            self.logger.warning(f"Gemini failed, falling back to NVIDIA NIM: {e}")
            from openai import AsyncOpenAI
            nvidia_keys = self.config.get("nvidia_api_key", [])
            nv_key = nvidia_keys[0] if isinstance(nvidia_keys, list) and nvidia_keys else nvidia_keys
            openai_client = AsyncOpenAI(api_key=nv_key, base_url="https://integrate.api.nvidia.com/v1")
            response = await openai_client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048
            )
            sql = response.choices[0].message.content.strip()

        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.endswith("```"):
            sql = sql[:-3]
        return sql.strip()

    @observe(name="traceroot_analyst.execute_sql", type="tool")
    async def _execute_sql(self, sql: str) -> Dict[str, Any]:
        # For now, we mock the Traceroot API since the feature is still in PRs (#1337, #1340)
        # If the API key is present, we would do:
        # async with httpx.AsyncClient() as client:
        #     resp = await client.post(self.base_url, json={"query": sql}, headers={"Authorization": f"Bearer {self.api_key}"})
        #     return resp.json()
        
        self.logger.info(f"Mocking Traceroot SQL execution for: {sql}")
        return {
            "columns": ["metric", "value"],
            "rows": [["average_duration_ms", 124.5], ["total_spans", 42]],
            "mocked": True
        }

    @observe(name="traceroot_analyst.summarize", type="llm")
    async def _summarize_results(self, question: str, data: Dict[str, Any]) -> str:
        prompt = f"""
Given the user's question and the SQL data result, provide a brief, helpful summary.
Question: {question}
Data: {json.dumps(data)}
"""
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            self.logger.warning(f"Gemini failed, falling back to NVIDIA NIM: {e}")
            from openai import AsyncOpenAI
            # NVIDIA API uses the OpenAI python client format
            nvidia_keys = self.config.get("nvidia_api_key", [])
            nv_key = nvidia_keys[0] if isinstance(nvidia_keys, list) and nvidia_keys else nvidia_keys
            openai_client = AsyncOpenAI(api_key=nv_key, base_url="https://integrate.api.nvidia.com/v1")
            response = await openai_client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048
            )
            return response.choices[0].message.content.strip()
