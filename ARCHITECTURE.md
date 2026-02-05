
# Architecture Guide

This document explains the high-level design of the Todoist Gemini Pipeline. It is intended for developers who want to understand *how* the application works under the hood.

## 🗺 System Overview

The application follows a **Layered Architecture**:

```mermaid
graph TD
    User[User] --> GUI[GUI Layer (PySide6)]
    GUI --> Core[Core Logic Layer]
    Core --> Orchestrator[Orchestrator]
    Core --> Engine[Weekly Review Engine]
    Orchestrator --> Todoist[Todoist Client]
    Orchestrator --> Gemini[Gemini Client]
    Engine --> Profile[Profile & Rules]
```

### 1. GUI Layer (`app/gui/`)

* **Technology**: PySide6 (Qt for Python).
* **Responsibility**: Rendering UI, handling user input, and managing background threads.
* **Key Files**:
  * `main_window.py`: The root window. Wires everything together.
  * `worker.py`: Handles threading. **Critically**, all network calls (Gemini/Todoist) must run here to avoid freezing the UI.
  * `weekly_review_tab.py`: The wizard interface for the weekly review.

### 2. Core Logic Layer (`app/core/`)

* **Responsibility**: Business logic, state management, and orchestration. UI-agnostic.
* **Key Files**:
  * `orchestrator.py`: The "Brain". Manages the chat session, fetches state, and executes actions.
  * `schemas.py`: Shared data models (`State`, `Action`, `Task`).
  * `todoist_client.py`: Wrapper around the official Todoist API.
  * `gemini_client.py`: Wrapper around the Google Generative AI SDK.

### 3. Weekly Review Engine (`app/core/weekly_review/`)

* **Responsibility**: A specialized sub-module for the Weekly Review workflow.
* **Key Concept**: It functions like a State Machine.
* **Flow**: `Start Session` -> `Get Step ViewModel` -> `User Input` -> `Complete Step` -> `Save Session`.
* **Persistence**: Saves sessions to local JSON files (`ReviewSession`) to avoid cluttering Todoist with metadata.

## 🏗 Data Structures

### The `State` Object

The entire "World View" of the application is encapsulated in the `State` object.

```python
@dataclass
class State:
    tasks: List[Dict]       # Raw tasks from Todoist
    projects: List[Dict]    # Raw projects
    sections: List[Dict]    # Raw sections
    formatted_context: str  # String representation optimized for LLM consumption
```

### The `Action` Object

The bridge between Intent and Execution. The AI outputs JSON which is parsed into these objects.

```python
class Action(TypedDict):
    type: str     # e.g., "update_task"
    id: str       # e.g., "12345"
    ...           # specific params
```

## 📖 The "Tour Guide" Pattern

You will notice a large header block at the top of comprehensive files:

```python
# =================================================================================================
# TOUR HEADER: [Module Name]
# =================================================================================================
#
# JOB: What this file does.
#
# KEY CONCEPTS: Important things to know.
# ...
```

**Why?**
This codebase is designed to be **Self-Documenting**. When reading a file, start with the Tour Header to ground yourself before diving into the implementation details.

## 📂 Directory Map

```text
.
├── app/
│   ├── core/               # Business Logic
│   │   ├── weekly_review/  # Weekly Review Engine
│   │   ├── orchestrator.py # Main Controller
│   │   └── ...
│   ├── gui/                # PySide6 Frontend
│   │   ├── main_window.py  # Entry point
│   │   └── ...
│   ├── main.py             # App Entry Point
│   └── profile/            # User-specific config (kyle.json)
├── tests/                  # Unit and Integration Tests
├── .env                    # Secrets (Not committed)
└── requirements.txt        # Dependencies
```
