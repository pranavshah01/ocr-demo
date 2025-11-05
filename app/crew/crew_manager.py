"""CrewAI orchestration and execution."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from crewai import Crew
from typing import List, Dict, Any, Optional
from app.crew.tasks import TaskFactory
from app.crew.agents import AgentFactory


class CrewManager:
    """Manages CrewAI crew execution."""

    def __init__(self):
        self.task_factory = TaskFactory()
        self.agent_factory = AgentFactory()
        # Use up to 3 workers for better concurrency
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def create_crew(self, tasks: List) -> Crew:
        """Create a crew with given tasks."""
        return Crew(
            agents=[task.agent for task in tasks],
            tasks=tasks,
            verbose=False,  # Disable verbose mode for faster execution
            process="sequential",  # Use sequential processing (faster than hierarchical)
            memory=False,  # Disable crew memory (reduces overhead)
            max_rpm=100  # Allow more requests per minute (default is 10)
        )
    
    def _execute_crew_sync(self, crew: Crew) -> Dict[str, Any]:
        """Execute crew synchronously (runs in thread)."""
        try:
            from app.config import settings
            import threading
            import queue
            
            result_queue = queue.Queue()
            
            def run_crew():
                try:
                    result = crew.kickoff()
                    result_queue.put(("success", result))
                except Exception as e:
                    result_queue.put(("error", str(e)))
            
            thread = threading.Thread(target=run_crew, daemon=True)
            thread.start()
            thread.join(timeout=settings.crewai_timeout)
            
            if thread.is_alive():
                # Thread is still running - timed out
                return {
                    "success": False,
                    "result": None,
                    "error": f"CrewAI execution timed out after {settings.crewai_timeout} seconds"
                }
            
            # Get result from queue
            try:
                status, value = result_queue.get(timeout=1)
                if status == "error":
                    return {
                        "success": False,
                        "result": None,
                        "error": value
                    }
                else:
                    return {
                        "success": True,
                        "result": value,
                        "error": None
                    }
            except queue.Empty:
                return {
                    "success": False,
                    "result": None,
                    "error": "CrewAI execution completed but no result available"
                }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
    
    async def execute_crew(self, crew: Crew) -> Dict[str, Any]:
        """Execute crew asynchronously (runs in thread pool)."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._execute_crew_sync,
            crew
        )
        return result

