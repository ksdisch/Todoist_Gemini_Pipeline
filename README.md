
# Todoist Gemini Pipeline

A powerful productivity assistant that bridges **Todoist** (System of Record) with **Google Gemini** (System of Intelligence) to empower a GTD-style Weekly Review and natural language task management.

## 🚀 Features

* **Natural Language Actions**: Chat with your Todoist. "Move all my low priority functionality tasks to next week" becomes a sequence of API calls.
* **Weekly Review Wizard**: A structured, step-by-step workflow (Get Clear -> Active Honesty -> Plan Next Week) driven by a dedicated GUI.
* **Safe Execution**: All AI-proposed actions are shown in a "Dry Run" mode first. You review and approve every change before it touches your real data.
* **AI Coach**: Context-aware help during your review. The AI sees your overdue tasks and helps you negotiate with yourself.

## 🛠 Prerequisites

* **Python 3.10+**
* **Todoist API Token**: [Get it here](https://todoist.com/app/settings/integrations/developer)
* **Google Gemini API Key**: [Get it here](https://aistudio.google.com/app/apikey)

## 📦 Installation

1. **Clone the repository**:

    ```bash
    git clone <repository-url>
    cd Todoist_Gemini_Pipeline
    ```

2. **Create a Virtual Environment** (Recommended):

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3. **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

4. **Configuration**:
    Create a `.env` file in the project root:

    ```env
    TODOIST_API_TOKEN=your_todoist_token_here
    GEMINI_API_KEY=your_gemini_key_here
    ```

## 🖥 Usage

### Launch the GUI

The main entry point is the PySide6 desktop application:

```bash
python app/main.py
```

### CLI Analyst (Legacy)

You can also run the terminal-based analyst for quick checks:

```bash
python todo_analyst.py
```

## 🏗 Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deep dive into the system design, core logic, and "Tour Guide" code documentation pattern.
