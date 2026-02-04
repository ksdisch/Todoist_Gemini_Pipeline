
import pytest
from unittest.mock import MagicMock, patch
from app.core.schemas import Action
from app.core import todoist_client
from app.core.orchestrator import Architect    

@pytest.fixture
def mock_requests():
    with patch("app.core.todoist_client.requests") as mock:
        yield mock

def test_handle_create_task_undo(mock_requests):
    # Setup
    mock_post = mock_requests.post.return_value
    mock_post.json.return_value = {"id": "12345"}
    mock_post.raise_for_status = MagicMock()
    
    action = {"type": "create_task", "content": "Test Task"}
    
    # Execute
    status, msg, api, undo_action = todoist_client.handle_create_task(action, {}, dry_run=False)
    
    # Verify
    assert status == "success"
    assert undo_action == {"type": "delete_task", "id": "12345"}

def test_handle_update_task_undo(mock_requests):
    # Setup
    mock_get = mock_requests.get.return_value
    mock_get.json.return_value = {"content": "Old Name", "priority": 1}
    
    mock_post = mock_requests.post.return_value
    mock_post.raise_for_status = MagicMock()
    
    action = {"type": "update_task", "id": "123", "content": "New Name"}
    
    # Execute
    status, msg, api, undo_action = todoist_client.handle_update_task(action, {}, dry_run=False)
    
    # Verify
    assert status == "success"
    assert undo_action == {"type": "update_task", "id": "123", "content": "Old Name"}
    # Verify we fetched before update
    mock_requests.get.assert_called_once()

def test_handle_close_task_undo(mock_requests):
    # Setup
    mock_post = mock_requests.post.return_value
    mock_post.raise_for_status = MagicMock()
    
    action = {"type": "close_task", "id": "123"}
    
    # Execute
    status, msg, api, undo_action = todoist_client.handle_close_task(action, {}, dry_run=False)
    
    # Verify
    assert status == "success"
    assert undo_action == {"type": "reopen_task", "id": "123"}

def test_orchestrator_undo_stack(mock_requests):
    architect = Architect()
    
    # Mock handlers to return undo actions
    with patch("app.core.todoist_client.execute_todoist_action") as mock_exec:
        # First execution: Create Task
        mock_exec.side_effect = [
            ("success", "Created", "API", {"type": "delete_task", "id": "101"})
        ]
        
        architect.execute([{"type": "create_task", "content": "A"}])
        
        # Check stack
        assert len(architect._undo_stack) == 1
        assert architect.get_undo_actions() == [{"type": "delete_task", "id": "101"}]
        
        # Second execution: Update Task
        mock_exec.side_effect = [
             ("success", "Updated", "API", {"type": "update_task", "id": "101", "content": "Old"})
        ]
        architect.execute([{"type": "update_task", "id": "101", "content": "New"}])
        
        # Check stack
        assert len(architect._undo_stack) == 2
        assert architect.get_undo_actions() == [{"type": "update_task", "id": "101", "content": "Old"}]
        
        # Undo last run
        mock_exec.side_effect = None # Reset side effect for undo (since perform_undo calls execute_todoist_action)
        mock_exec.return_value = ("success", "Undone", "API", None)
        
        architect.perform_undo()
        
        # Check stack pop
        assert len(architect._undo_stack) == 1
        # Check previous is now top
        assert architect.get_undo_actions() == [{"type": "delete_task", "id": "101"}]
