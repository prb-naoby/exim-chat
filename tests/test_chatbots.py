import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock Streamlit and other dependencies
sys.modules['streamlit'] = MagicMock()
import streamlit as st

# Mock database
sys.modules['modules.database'] = MagicMock()
from modules import database

class TestChatbotLogic(unittest.TestCase):
    def setUp(self):
        # Reset session state mock
        st.session_state = {}
        
        # Mock database functions
        database.save_message = MagicMock()
        database.update_session_title = MagicMock()
        database.clear_chat_history = MagicMock()

    def test_add_user_message(self):
        """Test adding a user message to state"""
        st.session_state['messages'] = []
        
        content = "Hello"
        timestamp = "2023-01-01 12:00:00"
        
        # Simulate adding message
        st.session_state['messages'].append({
            "role": "user",
            "content": content,
            "timestamp": timestamp
        })
        
        self.assertEqual(len(st.session_state['messages']), 1)
        self.assertEqual(st.session_state['messages'][0]['content'], "Hello")

    def test_edit_message_logic(self):
        """Test logic for editing a message and regenerating response"""
        # Initial state: User msg + Assistant msg
        st.session_state['messages'] = [
            {"role": "user", "content": "Original", "timestamp": "t1"},
            {"role": "assistant", "content": "Response 1", "timestamp": "t2"}
        ]
        
        # Edit index 0
        edit_index = 0
        new_content = "Edited"
        
        # Logic: Update content, truncate list, regenerate
        st.session_state['messages'][edit_index]["content"] = new_content
        # Truncate after the edited message (keep the edited one)
        st.session_state['messages'] = st.session_state['messages'][:edit_index+1]
        
        self.assertEqual(len(st.session_state['messages']), 1)
        self.assertEqual(st.session_state['messages'][0]['content'], "Edited")
        
        # Simulate regeneration
        new_response = "Response 2"
        st.session_state['messages'].append({
            "role": "assistant",
            "content": new_response,
            "timestamp": "t3"
        })
        
        self.assertEqual(len(st.session_state['messages']), 2)
        self.assertEqual(st.session_state['messages'][1]['content'], "Response 2")

    def test_regenerate_logic(self):
        """Test logic for regenerating the last response"""
        # Initial state: User msg + Assistant msg
        st.session_state['messages'] = [
            {"role": "user", "content": "Question", "timestamp": "t1"},
            {"role": "assistant", "content": "Bad Response", "timestamp": "t2"}
        ]
        
        # Regenerate means: Remove last assistant message, re-run logic for last user message
        # In the UI code, this is triggered by a button on the USER message (index 0)
        user_msg_index = 0
        
        # Logic: Truncate after user message
        st.session_state['messages'] = st.session_state['messages'][:user_msg_index+1]
        
        self.assertEqual(len(st.session_state['messages']), 1)
        self.assertEqual(st.session_state['messages'][0]['role'], "user")
        
        # Simulate new response
        st.session_state['messages'].append({
            "role": "assistant",
            "content": "Better Response",
            "timestamp": "t3"
        })
        
        self.assertEqual(st.session_state['messages'][1]['content'], "Better Response")

    def test_insw_guardrails(self):
        """Test INSW guardrails and HS code logic"""
        # Mock dependencies
        from modules import insw_chatbot
        
        # Test 1: Short input guardrail
        result_short = insw_chatbot.search_insw_regulation("a")
        self.assertIn("lebih spesifik", result_short)
        
        # Test 2: HS Code auto-detection logic
        # We need to mock create_embedding and search_hybrid to verify the query transformation
        insw_chatbot.chatbot_utils.create_embedding = MagicMock(return_value=[0.1]*768)
        insw_chatbot.insw_store.search_hybrid = MagicMock(return_value=[])
        
        # This should trigger the "hs code" prefix logic
        insw_chatbot.search_insw_regulation("12345678")
        
        # Verify create_embedding was called with "hs code 12345678"
        insw_chatbot.chatbot_utils.create_embedding.assert_called_with(insw_chatbot.client, "hs code 12345678")

if __name__ == '__main__':
    unittest.main()
