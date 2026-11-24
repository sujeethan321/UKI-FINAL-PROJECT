"""Pure AI tests without backend/tests/conftest.py or real configuration.

The existing offline harness replaces the DB/config and blocks networking.
Load only Settings definitions (not the singleton); every adapter uses mocks.
"""
import ast,os,sys,types
from pathlib import Path
from unittest.mock import patch
import subscription_suite as base

def run():
    path=Path(__file__).parents[1]/'app/core/config.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    tree.body=[node for node in tree.body if not (isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='settings' for t in node.targets))]
    definitions=types.ModuleType('offline_ai_settings');definitions.__file__=str(path);sys.modules[definitions.__name__]=definitions
    # Isolate test Settings from operator process variables and dotenv.
    with patch.dict(os.environ,{},clear=True):
        exec(compile(tree,str(path),'exec'),definitions.__dict__)
        base.config.Settings=definitions.Settings
        base.config.load_settings=definitions.load_settings
        import pytest
        return pytest.main(['--noconftest','-q','-p','no:cacheprovider',
            'backend/tests/test_ai_config.py','backend/tests/test_groq_client.py','backend/tests/test_tamil_credit_summary_prompt.py',
            'backend/tests/test_tamil_credit_summary_service.py','backend/tests/test_customer_financial_snapshot_service.py'])

if __name__=='__main__':sys.exit(run())
