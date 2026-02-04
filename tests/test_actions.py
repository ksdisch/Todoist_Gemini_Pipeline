import pytest
from unittest.mock import MagicMock, patch
from app.core.todoist_client import execute_todoist_action, handle_close_task, handle_create_project, ACTION_REGISTRY

# Test Registry
def test_action_registry_contains_actions():
    assert "close_task" in ACTION_REGISTRY
    assert "create_project" in ACTION_REGISTRY

# Test Validation
def test_close_task_validation():
    with pytest.raises(ValueError, match="Missing 'id'"):
        handle_close_task({}, {})

# Test Execution Logic (Mocking Requests)
@patch('requests.post')
def test_handle_create_project(mock_post):
    headers = {"Authorization": "Bearer token"}
    action = {"type": "create_project", "name": "New Project"}
    
    # Setup mock
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Execute
    status, msg, api = handle_create_project(action, headers)

    # Verify
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['json'] == {"name": "New Project"}
    assert kwargs['headers'] == headers
    assert status == "success"

@patch('requests.post')
def test_execute_todoist_action(mock_post):
    action = {"type": "close_task", "id": "123"}
    
    mock_response = MagicMock()
    mock_post.return_value = mock_response
    
    status, msg, api_call = execute_todoist_action(action, "fake_token")
    
    mock_post.assert_called_once()
    assert "tasks/123/close" in mock_post.call_args[0][0]
    assert status == "success"

def test_dry_run_execution():
    action = {"type": "create_project", "name": "Simulated Project"}
    
    # Execute with dry_run=True
    # We do NOT mock requests because dry_run should not call them.
    # If it does, it will fail (connection error) or we can mock to ensure not called.
    
    with patch('requests.post') as mock_post:
        status, msg, api_call = execute_todoist_action(action, "fake_token", dry_run=True)
        
        mock_post.assert_not_called()
        assert status == "simulated"
        assert "Would create project 'Simulated Project'" in msg
        assert "POST https://api.todoist.com/rest/v2/projects" in api_call
