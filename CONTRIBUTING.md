# Contributing to VitaGraph AI

First off, thank you for considering contributing to VitaGraph AI! It's people like you that make DeSci such a great community.

## Development Setup

1. **Fork and Clone** the repository.
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Workflow

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes.
3. Ensure all tests pass. We use `pytest` for all unit testing.
   ```bash
   pytest tests/
   ```
   **Note**: All new features must include passing unit tests. If you are interacting with external services (like the Neo4j database or the Gemini API), please use `unittest.mock` to mock the responses.
4. If you modified `schemas.py`, ensure that you are strictly using `Enum` classes for biological vocabularies to prevent graph fragmentation.
5. Commit your changes with a descriptive message.
6. Push to your fork and submit a Pull Request.

## Code Style
- Please ensure your code is cleanly formatted and includes docstrings for all major functions.
- Use `logging` instead of standard `print()` statements for pipeline output.

## Reporting Bugs
If you find a bug or have a feature request, please open an issue on GitHub. Include as much detail as possible, including steps to reproduce the issue and your current environment setup.
