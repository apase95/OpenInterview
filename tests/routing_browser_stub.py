"""Explicit loopback-only browser test harness. Fake identities, no Google/DB.

Never loaded by backend.api. Run: python -m tests.routing_browser_stub
"""
import os
import uvicorn
from backend.api import app
from backend import auth, workspace
from tests.test_google_auth import ENV
from tests.workspace_fixture import MemoryAuth, MemoryWorkspace

if __name__ == '__main__':
    os.environ.update({**ENV, 'APP_ORIGIN': 'http://127.0.0.1:3001'})
    auth.store = MemoryAuth()
    auth.Settings.cookie = property(lambda self: 'oi_routing_test')
    workspace.store = MemoryWorkspace()
    uvicorn.run(app, host='127.0.0.1', port=8011, access_log=False)
