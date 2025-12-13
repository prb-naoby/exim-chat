"""
LLM Logger Module - Track all LLM interactions for developer dashboard
Logs: requests, responses, token usage, latency, errors
"""
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from modules.database import SQLITE_DB_PATH
import sqlite3

class LLMLogger:
    """Logger for tracking LLM calls and token usage"""
    
    STATUS_ANSWERED = "answered"
    STATUS_UNANSWERED = "unanswered"
    STATUS_ERROR = "error"
    
    @staticmethod
    def log_call(
        session_id: str,
        username: str,
        chatbot_type: str,
        status: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        error_message: Optional[str] = None,
        query: Optional[str] = None
    ) -> bool:
        """Log an LLM call to the database"""
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT INTO llm_logs 
                (session_id, username, chatbot_type, status, input_tokens, output_tokens, 
                 latency_ms, error_message, query)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, username, chatbot_type, status, input_tokens, output_tokens,
                  latency_ms, error_message, query[:500] if query else None))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error logging LLM call: {e}")
            return False
    
    @staticmethod
    def get_logs(
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        chatbot_type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get paginated LLM logs"""
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = "SELECT * FROM llm_logs WHERE 1=1"
            params = []
            
            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)
            if chatbot_type_filter:
                query += " AND chatbot_type = ?"
                params.append(chatbot_type_filter)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            c.execute(query, params)
            logs = [dict(row) for row in c.fetchall()]
            conn.close()
            return logs
        except Exception as e:
            print(f"Error getting LLM logs: {e}")
            return []
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get aggregate statistics for developer dashboard"""
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            c = conn.cursor()
            
            # Total counts by status
            c.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'answered' THEN 1 ELSE 0 END) as answered,
                    SUM(CASE WHEN status = 'unanswered' THEN 1 ELSE 0 END) as unanswered,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    AVG(latency_ms) as avg_latency_ms
                FROM llm_logs
            """)
            row = c.fetchone()
            
            # Daily stats for chart (last 7 days)
            c.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as calls,
                    SUM(input_tokens + output_tokens) as tokens
                FROM llm_logs
                WHERE created_at >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """)
            daily_stats = [{"date": r[0], "calls": r[1], "tokens": r[2]} for r in c.fetchall()]
            
            conn.close()
            
            return {
                "total": row[0] or 0,
                "answered": row[1] or 0,
                "unanswered": row[2] or 0,
                "errors": row[3] or 0,
                "total_input_tokens": row[4] or 0,
                "total_output_tokens": row[5] or 0,
                "avg_latency_ms": round(row[6] or 0, 2),
                "daily_stats": daily_stats
            }
        except Exception as e:
            print(f"Error getting LLM stats: {e}")
            return {
                "total": 0, "answered": 0, "unanswered": 0, "errors": 0,
                "total_input_tokens": 0, "total_output_tokens": 0,
                "avg_latency_ms": 0, "daily_stats": []
            }

# Helper class for timing LLM calls
class LLMCallTimer:
    """Context manager for timing LLM calls"""
    def __init__(self):
        self.start_time = None
        self.latency_ms = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.latency_ms = int((time.time() - self.start_time) * 1000)
        return False

# Global instance
llm_logger = LLMLogger()
