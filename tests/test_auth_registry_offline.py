import json
import tempfile
import unittest
from pathlib import Path
from services.auth import UserStore, AuthError
from services.app_registry import AppRegistry
from services.offline_assistant import respond

class AuthRegistryOfflineTests(unittest.TestCase):
    def test_password_verifier_and_login(self):
        with tempfile.TemporaryDirectory() as td:
            store = UserStore(Path(td) / 'users.json')
            store.create_user('test_admin', 'a-long-test-password', 'admin')
            raw = json.loads((Path(td) / 'users.json').read_text())
            self.assertNotIn('password', raw['users']['test_admin'])
            self.assertNotIn('a-long-test-password', (Path(td) / 'users.json').read_text())
            self.assertEqual(store.authenticate('TEST_ADMIN', 'a-long-test-password')['role'], 'admin')
            self.assertIsNone(store.authenticate('test_admin', 'incorrect password'))

    def test_app_registry_adds_without_executing(self):
        with tempfile.TemporaryDirectory() as td:
            registry = AppRegistry(Path(td))
            item = registry.add_app('demo-app', 'Demo App', 'test app', 'https://example.com', 'url')
            self.assertEqual(item['kind'], 'url')
            self.assertEqual(registry.list_apps()[0]['id'], 'demo-app')

    def test_app_registry_validates_python_entrypoint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = AppRegistry(root)
            with self.assertRaises(FileNotFoundError):
                registry.add_app('missing-app', 'Missing', 'missing entry', str(root / 'missing.py'), 'python')
            script = root / 'demo.py'
            script.write_text('print("safe test")', encoding='utf-8')
            item = registry.add_app('demo-python', 'Demo Python', 'test app', str(script), 'python')
            self.assertEqual(Path(item['entrypoint']), script)
            self.assertTrue(Path(item['entrypoint']).is_file())

    def test_offline_assistant_needs_no_network(self):
        self.assertIn('84', respond('/calc 12 * 7'))
        self.assertIn('not a trained', respond('/help'))

if __name__ == '__main__': unittest.main()
