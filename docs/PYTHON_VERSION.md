# Python Version Requirements

## TL;DR
**Use Python 3.11** - it's the sweet spot for this project.

## Compatibility Matrix

| Component | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12+ |
|-----------|-----------|-------------|-------------|--------------|
| Modal SDK | ✅ | ✅ | ✅ | ✅ |
| Anthropic | ✅ | ✅ | ✅ | ✅ |
| Flask | ✅ | ✅ | ✅ | ✅ |
| Whisper (faster-whisper) | ✅ | ✅ | ✅ | ❌ |
| TTS (Coqui) | ✅ | ✅ | ✅ | ❌ |
| Librosa | ✅ | ✅ | ✅ | ⚠️ |
| **Recommended** | ⚠️ | ✅ | ✅✅✅ | ❌ |

## Current Situation

You have **Python 3.14** installed, which is too new for AI/ML packages.

## Options

### Option 1: Install Python 3.11 (RECOMMENDED)

**Best choice for full functionality**

1. Download Python 3.11.9 from:
   https://www.python.org/downloads/release/python-3119/

2. Install it (check "Add to PATH")

3. Recreate your venv:
   ```bash
   # Delete old venv
   Remove-Item -Recurse -Force venv

   # Create with Python 3.11
   py -3.11 -m venv venv

   # Activate
   .\venv\Scripts\Activate.ps1

   # Install
   pip install -r requirements-py311.txt
   ```

### Option 2: Deploy-Only Mode (Python 3.12+)

**Skip local STT/TTS, only deploy to Modal**

With your Python 3.14:
```bash
# Install minimal requirements
pip install -r requirements-modal-only.txt
```

**What works:**
- ✅ Deploy Whisper and TTS to Modal
- ✅ Use Flask API (calls Modal services remotely)
- ✅ Claude API integration
- ❌ Can't test Whisper/TTS locally
- ❌ Can't run full integration tests

### Option 3: Use Docker (Advanced)

Run everything in a container with Python 3.11:
```bash
# Coming soon - Docker setup for this project
```

## Checking Your Python Versions

```bash
# Windows
py -0

# Should show something like:
# -3.14-64 *
# -3.11-64
# -3.10-64
```

## Which Option Should You Choose?

**If you want to:**
- ✅ Test everything locally → **Option 1** (Python 3.11)
- ✅ Just deploy and test via API → **Option 2** (Current Python)
- ✅ Learn Docker → **Option 3** (Advanced)

## After Installing Python 3.11

Update your IDE/VS Code Python interpreter:
1. Press Ctrl+Shift+P
2. Type "Python: Select Interpreter"
3. Choose Python 3.11

## Questions?

See QUICKSTART.md for setup instructions with Python 3.11.
