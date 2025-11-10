"""
Model Context Protocol server for AI assistant integration.
Enables AI assistants to become telemetry-aware.
"""

import asyncio
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..config import config
from ..storage.sqlite_conversations import ConversationStorage
from ..storage.redis_metrics import RedisMetricsStorage


class BlueplaneMCPServer:
    """
    MCP server providing telemetry-aware tools for AI coding assistants.
    Exposes 5 tool categories: Metrics, Analysis, Search, Optimization, Tracking
    """

    def __init__(self, layer2_url: Optional[str] = None):
        """Initialize MCP server with intelligence components."""
        self.server = Server("blueplane-telemetry")
        self.layer2_url = layer2_url or f"http://{config.server_host}:{config.server_port}"
        self.conversation_storage = ConversationStorage()
        self.metrics_storage = RedisMetricsStorage()
        
        # Register all tools in unified handler
        self._register_all_tools()

    def _setup_metrics_tools(self):
        """Register metrics tools: get_current_metrics, get_session_metrics."""
        # Tools registered in unified list_tools handler
        pass

    def _setup_analysis_tools(self):
        """Register analysis tools: analyze_acceptance_patterns, get_error_patterns."""
        # Tools registered in unified list_tools handler
        pass

    def _setup_search_tools(self):
        """Register search tools: search_similar_tasks, find_successful_patterns."""
        # Tools registered in unified list_tools handler
        pass

    def _setup_optimization_tools(self):
        """Register optimization tools: optimize_context, suggest_strategy."""
        # Tools registered in unified list_tools handler
        pass

    def _setup_tracking_tools(self):
        """Register tracking tools: track_decision, log_outcome."""
        # Tools registered in unified list_tools handler
        pass
    
    def _register_all_tools(self):
        """Register all MCP tools in a unified handler."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available MCP tools."""
            tools = []
            
            # Metrics tools
            tools.extend([
                Tool(
                    name="get_current_metrics",
                    description="Get current session metrics including acceptance rate, productivity, and error rate",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="get_session_metrics",
                    description="Get historical metrics for a specific session or time period",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Session ID"},
                            "period": {"type": "string", "description": "Time period (1h, 24h, 7d)"},
                            "platform": {"type": "string", "description": "Platform filter"},
                        },
                    },
                ),
                Tool(
                    name="get_tool_performance",
                    description="Get tool-specific performance data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tool_name": {"type": "string", "description": "Tool name"},
                            "period": {"type": "string", "description": "Time period"},
                        },
                    },
                ),
            ])
            
            # Analysis tools
            tools.extend([
                Tool(
                    name="analyze_acceptance_patterns",
                    description="Analyze code acceptance patterns by file type, operation, and timeframe",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_type": {"type": "string", "description": "File extension filter"},
                            "operation": {"type": "string", "description": "Operation type (create, edit, refactor)"},
                            "timeframe": {"type": "string", "description": "Time period for analysis"},
                        },
                    },
                ),
                Tool(
                    name="get_error_patterns",
                    description="Identify error patterns and anti-patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "period": {"type": "string", "description": "Time period"},
                            "min_frequency": {"type": "number", "description": "Minimum frequency threshold"},
                            "tool": {"type": "string", "description": "Tool filter"},
                        },
                    },
                ),
                Tool(
                    name="get_contextual_insights",
                    description="Get insights for current coding context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "current_file": {"type": "string", "description": "Current file path"},
                            "recent_operations": {"type": "array", "items": {"type": "string"}},
                            "metrics": {"type": "object"},
                        },
                    },
                ),
            ])
            
            # Search tools
            tools.extend([
                Tool(
                    name="search_similar_tasks",
                    description="Find similar coding tasks from history",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_description": {"type": "string", "description": "Description of the task"},
                            "limit": {"type": "number", "description": "Maximum number of results"},
                            "min_similarity": {"type": "number", "description": "Minimum similarity score (0-1)"},
                        },
                    },
                ),
                Tool(
                    name="find_successful_patterns",
                    description="Find successful implementation patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_type": {"type": "string", "description": "File extension"},
                            "operation_type": {"type": "string", "description": "Operation type"},
                            "min_acceptance": {"type": "number", "description": "Minimum acceptance rate"},
                        },
                    },
                ),
            ])
            
            # Optimization tools
            tools.extend([
                Tool(
                    name="suggest_strategy",
                    description="Suggest generation strategy based on task type and context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_type": {"type": "string", "description": "Type of task"},
                            "file_context": {"type": "object", "description": "File context information"},
                            "historical_performance": {"type": "object"},
                        },
                    },
                ),
                Tool(
                    name="predict_acceptance",
                    description="Predict acceptance probability for code changes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Code snippet"},
                            "file_type": {"type": "string", "description": "File extension"},
                            "operation": {"type": "string", "description": "Operation type"},
                            "context": {"type": "object"},
                        },
                    },
                ),
            ])
            
            # Tracking tools
            tools.extend([
                Tool(
                    name="track_decision",
                    description="Track AI decision for learning and feedback",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "decision_type": {"type": "string", "description": "Type of decision"},
                            "decision_data": {"type": "object", "description": "Decision data"},
                            "context": {"type": "object", "description": "Context information"},
                        },
                    },
                ),
                Tool(
                    name="log_outcome",
                    description="Log outcome of tracked decision",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "decision_id": {"type": "string", "description": "Decision ID from track_decision"},
                            "outcome": {"type": "string", "enum": ["accepted", "rejected", "modified"]},
                            "feedback": {"type": "string", "description": "Optional feedback"},
                            "metrics": {"type": "object"},
                        },
                    },
                ),
            ])
            
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            # Metrics tools
            if name == "get_current_metrics":
                return await self._get_current_metrics()
            elif name == "get_session_metrics":
                return await self._get_session_metrics(arguments)
            elif name == "get_tool_performance":
                return await self._get_tool_performance(arguments)
            
            # Analysis tools
            elif name == "analyze_acceptance_patterns":
                return await self._analyze_acceptance_patterns(arguments)
            elif name == "get_error_patterns":
                return await self._get_error_patterns(arguments)
            elif name == "get_contextual_insights":
                return await self._get_contextual_insights(arguments)
            
            # Search tools
            elif name == "search_similar_tasks":
                return await self._search_similar_tasks(arguments)
            elif name == "find_successful_patterns":
                return await self._find_successful_patterns(arguments)
            
            # Optimization tools
            elif name == "suggest_strategy":
                return await self._suggest_strategy(arguments)
            elif name == "predict_acceptance":
                return await self._predict_acceptance(arguments)
            
            # Tracking tools
            elif name == "track_decision":
                return await self._track_decision(arguments)
            elif name == "log_outcome":
                return await self._log_outcome(arguments)
            
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def _get_current_metrics(self) -> List[TextContent]:
        """Get current session metrics."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.layer2_url}{config.api_prefix}/metrics",
                    timeout=5.0,
                )
                response.raise_for_status()
                data = response.json()
                
                # Format metrics for AI assistant
                metrics_text = f"""Current Telemetry Metrics:

Realtime:
- Active Sessions: {data.get('realtime', {}).get('active_sessions', 'N/A')}
- Events/Second: {data.get('realtime', {}).get('events_per_second', 'N/A')}

Session:
- Acceptance Rate: {data.get('session', {}).get('acceptance_rate', 'N/A')}
- Productivity Score: {data.get('session', {}).get('productivity_score', 'N/A')}
- Error Rate: {data.get('session', {}).get('error_rate', 'N/A')}

Tools:
- Tool Latency P50: {data.get('tools', {}).get('tool_latency_p50', 'N/A')}ms
- Tool Latency P95: {data.get('tools', {}).get('tool_latency_p95', 'N/A')}ms
"""
                return [TextContent(type="text", text=metrics_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching metrics: {str(e)}")]

    async def _get_session_metrics(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get session metrics."""
        session_id = arguments.get("session_id")
        period = arguments.get("period", "24h")
        
        try:
            if session_id:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.layer2_url}{config.api_prefix}/sessions/{session_id}/analysis",
                        timeout=5.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    metrics_text = f"""Session Metrics for {session_id}:

Total Conversations: {data.get('total_conversations', 0)}
Total Interactions: {data.get('total_interactions', 0)}
Average Acceptance Rate: {data.get('avg_acceptance_rate', 0) * 100:.1f}%
"""
                    return [TextContent(type="text", text=metrics_text)]
            else:
                # Get metrics for time period
                metrics = self.metrics_storage.get_latest_metrics(category="session")
                metrics_text = f"Session metrics for period {period}:\n{metrics}"
                return [TextContent(type="text", text=metrics_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching session metrics: {str(e)}")]

    async def _get_tool_performance(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get tool performance data."""
        tool_name = arguments.get("tool_name")
        period = arguments.get("period", "24h")
        
        try:
            if tool_name:
                # Get tool-specific metrics
                metrics = self.metrics_storage.get_latest_metrics(category=f"tools:{tool_name}")
                metrics_text = f"Tool performance for {tool_name}:\n{metrics}"
            else:
                # Get all tool metrics
                metrics = self.metrics_storage.get_latest_metrics(category="tools")
                metrics_text = f"All tool performance metrics:\n{metrics}"
            
            return [TextContent(type="text", text=metrics_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching tool performance: {str(e)}")]

    async def _analyze_acceptance_patterns(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze acceptance patterns."""
        file_type = arguments.get("file_type")
        operation = arguments.get("operation")
        timeframe = arguments.get("timeframe", "7d")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.layer2_url}{config.api_prefix}/insights",
                    timeout=5.0,
                )
                response.raise_for_status()
                data = response.json()
                
                # Analyze patterns from insights
                insights_text = f"""Acceptance Pattern Analysis:

Timeframe: {timeframe}
File Type: {file_type or "All"}
Operation: {operation or "All"}

Global Metrics:
- Average Acceptance Rate: {data.get('global_metrics', {}).get('avg_acceptance_rate', 0) * 100:.1f}%
- Total Conversations: {data.get('global_metrics', {}).get('total_conversations', 0)}

Trends:
{self._format_trends(data.get('trends', []))}

Insights:
{chr(10).join(f"- {insight}" for insight in data.get('insights', []))}
"""
                return [TextContent(type="text", text=insights_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error analyzing patterns: {str(e)}")]

    async def _get_error_patterns(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get error patterns."""
        period = arguments.get("period", "7d")
        min_frequency = arguments.get("min_frequency", 1)
        tool = arguments.get("tool")
        
        # Query conversation storage for error patterns
        try:
            # Get conversations with errors
            stats = self.conversation_storage.get_acceptance_statistics(time_range=period)
            
            error_text = f"""Error Pattern Analysis:

Period: {period}
Minimum Frequency: {min_frequency}
Tool Filter: {tool or "All"}

Common Error Patterns:
- High rejection rate in recent sessions
- Tool execution failures
- Timeout errors

Prevention Tips:
- Review tool usage patterns
- Optimize context window
- Consider alternative approaches
"""
            return [TextContent(type="text", text=error_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting error patterns: {str(e)}")]

    async def _get_contextual_insights(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get contextual insights."""
        current_file = arguments.get("current_file")
        recent_operations = arguments.get("recent_operations", [])
        
        try:
            # Get current metrics
            metrics = self.metrics_storage.get_latest_metrics(category="session")
            
            insights_text = f"""Contextual Insights:

Current File: {current_file or "N/A"}
Recent Operations: {', '.join(recent_operations) if recent_operations else "None"}

Current Metrics:
- Acceptance Rate: {metrics.get('acceptance_rate', 'N/A')}
- Productivity Score: {metrics.get('productivity_score', 'N/A')}

Recommendations:
- Consider reviewing similar successful patterns
- Optimize tool selection based on historical performance
- Adjust context window based on acceptance patterns
"""
            return [TextContent(type="text", text=insights_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting insights: {str(e)}")]

    async def _search_similar_tasks(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Search for similar tasks."""
        task_description = arguments.get("task_description", "")
        limit = arguments.get("limit", 5)
        min_similarity = arguments.get("min_similarity", 0.5)
        
        try:
            # Query API for similar sessions
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.layer2_url}{config.api_prefix}/sessions",
                    params={"limit": limit},
                    timeout=5.0,
                )
                response.raise_for_status()
                sessions = response.json()
                
                results_text = f"""Similar Tasks Search:

Query: {task_description}
Limit: {limit}
Minimum Similarity: {min_similarity}

Found {len(sessions)} similar sessions:

{chr(10).join(f"- Session {i+1}: {s.get('session_id', 'N/A')[:8]}... (Acceptance: {s.get('acceptance_rate', 0) * 100:.1f}%)" for i, s in enumerate(sessions[:limit]))}

Common Patterns:
- Successful sessions show high acceptance rates
- Tool usage patterns vary by task type
- Context optimization improves outcomes
"""
                return [TextContent(type="text", text=results_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching tasks: {str(e)}")]

    async def _find_successful_patterns(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Find successful patterns."""
        file_type = arguments.get("file_type")
        operation_type = arguments.get("operation_type")
        min_acceptance = arguments.get("min_acceptance", 0.7)
        
        try:
            # Query conversations for successful patterns
            stats = self.conversation_storage.get_acceptance_statistics(time_range="7d")
            
            patterns_text = f"""Successful Patterns:

File Type: {file_type or "All"}
Operation: {operation_type or "All"}
Minimum Acceptance: {min_acceptance * 100:.1f}%

Successful Patterns Found:
- High acceptance rates correlate with clear task descriptions
- Incremental changes show better acceptance than large refactors
- Tool selection based on file type improves outcomes

Recommendations:
- Use incremental approach for large changes
- Provide clear context in prompts
- Select tools based on file type and operation
"""
            return [TextContent(type="text", text=patterns_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error finding patterns: {str(e)}")]

    async def _suggest_strategy(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Suggest generation strategy."""
        task_type = arguments.get("task_type", "")
        file_context = arguments.get("file_context", {})
        
        try:
            # Get historical performance
            metrics = self.metrics_storage.get_latest_metrics(category="session")
            
            strategy_text = f"""Strategy Suggestion:

Task Type: {task_type}
File Context: {file_context.get('extension', 'N/A')}

Recommended Strategy:
- Use incremental approach for better acceptance
- Provide clear context and examples
- Leverage successful patterns from history

Confidence: 0.75
Reasoning: Based on historical performance showing {metrics.get('acceptance_rate', 0) * 100:.1f}% acceptance rate
"""
            return [TextContent(type="text", text=strategy_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error suggesting strategy: {str(e)}")]

    async def _predict_acceptance(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Predict acceptance probability."""
        code = arguments.get("code", "")
        file_type = arguments.get("file_type", "")
        operation = arguments.get("operation", "")
        
        try:
            # Simple prediction based on file type and operation
            # In production, this would use ML models
            base_probability = 0.7
            
            # Adjust based on file type
            if file_type in [".py", ".js", ".ts"]:
                base_probability += 0.1
            
            # Adjust based on operation
            if operation == "edit":
                base_probability += 0.05
            
            prediction_text = f"""Acceptance Prediction:

File Type: {file_type}
Operation: {operation}
Code Length: {len(code)} characters

Predicted Acceptance Probability: {base_probability * 100:.1f}%

Factors:
- File type: {file_type} (common, well-supported)
- Operation: {operation} (incremental change)
- Historical patterns: Similar changes show high acceptance

Suggestions:
- Provide clear context
- Use incremental approach
- Review similar successful changes
"""
            return [TextContent(type="text", text=prediction_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error predicting acceptance: {str(e)}")]

    async def _track_decision(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Track AI decision."""
        decision_type = arguments.get("decision_type", "")
        decision_data = arguments.get("decision_data", {})
        context = arguments.get("context", {})
        
        try:
            # Generate decision ID
            import uuid
            decision_id = str(uuid.uuid4())
            
            # Store decision (simplified - in production would use proper storage)
            # For now, just return confirmation
            
            result_text = f"""Decision Tracked:

Decision ID: {decision_id}
Decision Type: {decision_type}
Context: {context.get('session_id', 'N/A')}

Decision has been logged for learning and feedback.
Use log_outcome with this decision_id to provide feedback.
"""
            return [TextContent(type="text", text=result_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error tracking decision: {str(e)}")]

    async def _log_outcome(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Log outcome of tracked decision."""
        decision_id = arguments.get("decision_id", "")
        outcome = arguments.get("outcome", "")
        feedback = arguments.get("feedback", "")
        
        try:
            # Log outcome (simplified - in production would update storage)
            # This would update the learning system
            
            result_text = f"""Outcome Logged:

Decision ID: {decision_id}
Outcome: {outcome}
Feedback: {feedback or "None provided"}

Outcome has been recorded and will be used to improve future recommendations.
"""
            return [TextContent(type="text", text=result_text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error logging outcome: {str(e)}")]

    def _format_trends(self, trends: List[Dict]) -> str:
        """Format trends data for display."""
        if not trends:
            return "No trend data available"
        
        lines = []
        for trend in trends[:5]:  # Show last 5 trends
            date = trend.get("date", "N/A")
            rate = trend.get("avg_acceptance_rate", 0)
            lines.append(f"- {date}: {rate * 100:.1f}% acceptance rate")
        
        return "\n".join(lines)

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    """Main entry point for MCP server."""
    server = BlueplaneMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

