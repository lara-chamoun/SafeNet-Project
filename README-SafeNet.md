# SafeNet AI — Setup and Run

SafeNet runs locally in your browser. Follow **only the section for your computer: Windows or macOS**.

## Before you start

1. Extract the ZIP. Do not run the project from inside the ZIP.
2. Open the inner `SafeNet_AI_Project` folder in VS Code — the folder containing `requirements.txt`, `start.ps1`, and this README.
3. Select **Terminal > New Terminal**. Run all commands below from that project folder.


You need **Python 3.11 or newer**. Dependency installation requires internet access.

## Windows — PowerShell

### First-time setup

Check your Python version:

```powershell
python --version
```

If Python is missing or older than 3.11, install a supported version from python.org. Enable **Add Python to PATH** if offered, then reopen VS Code.

Run the following commands **one at a time**. Wait for each to finish successfully before running the next:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

- The first command creates the project's Python environment.
- The second installs its required packages.
- The third starts SafeNet. No separate environment activation is needed.

Open **http://localhost:8000** in your browser.

### Every time afterward

Open PowerShell in the same project folder and run only:

```powershell
.\start.ps1
```

If PowerShell blocks the script, use this equivalent command instead:

```powershell
.\.venv\Scripts\python.exe -m safenet.web
```

## macOS — Terminal

### First-time setup

Check your Python version:

```bash
python3 --version
```

If Python is missing or older than 3.11, install a supported version from python.org, then reopen your terminal.

Run the following commands **one at a time**. Wait for each to finish successfully before running the next:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m safenet.web
```

These commands create the environment, install the packages, and start SafeNet. No separate activation is needed. `start.ps1` is the Windows launcher; macOS uses the Python command above.

Open **http://localhost:8000** in your browser.

### Every time afterward

Open a terminal in the same project folder and run only:

```bash
.venv/bin/python -m safenet.web
```

## Using and stopping SafeNet

- **Offline:** analyzes your message using local rules; no OpenAI API calls.
- **Live:** uses the API key in `.env`; requires internet access and available API credit.
- Keep the terminal open while using the app. Press **Ctrl+C** in that terminal to stop it, on either operating system.
- You do not need to recreate the environment or reinstall packages each time. Saved conversations remain available after restarting.

## Common startup problems

- **`requirements.txt` or `start.ps1` cannot be found:** your terminal is in the wrong folder. Open the folder containing those files before running the commands.
- **Installation fails:** stop at that command and resolve the error before starting SafeNet. Check your internet connection and Python version.
- **Port 8000 is already in use:** stop the other SafeNet terminal with **Ctrl+C**, or add `--port 8001` to your operating system's `python -m safenet.web` command and open **http://localhost:8001**.
