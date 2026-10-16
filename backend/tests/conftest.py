"""Settings shared by every test."""

import os

# Tests must never call the real model. An empty key in the environment takes
# priority over the key in .env, so every Settings() built during a test run
# has the AI layer switched off. Tests that need a model pass a fake.
os.environ["GEMINI_API_KEY"] = ""
