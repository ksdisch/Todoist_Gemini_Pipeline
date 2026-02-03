import pytest
from unittest.mock import MagicMock, patch
from src.actions import execute_todoist_action, handle_close_task, handle_create_project, ACTION_REGISTRY

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
    handle_create_project(action, headers)

    # Verify
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['json'] == {"name": "New Project"}
    assert kwargs['headers'] == headers

@patch('requests.post')
def test_execute_todoist_action(mock_post):
    action = {"type": "close_task", "id": "123"}
    
    mock_response = MagicMock()
    mock_post.return_value = mock_response
    
    execute_todoist_action(action, "fake_token")
    
    mock_post.assert_called_once()
    assert "tasks/123/close" in mock_post.call_args[0][0]
