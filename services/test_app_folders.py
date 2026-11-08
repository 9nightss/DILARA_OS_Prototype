import json
import tempfile
import unittest
from pathlib import Path

from services.app_folders import AppFolderStore, AppFolderError, classify_path, MAX_ENTRIES


class AppFolderTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.store = AppFolderStore(self.root / "state" / "app_folders.json", self.root)
        (self.root / "games").mkdir()
        (self.root / "games" / "tetris.py").write_text("print('hi')")
        (self.root / "games" / "run.bat").write_text("@echo off")

    def tearDown(self):
        self._td.cleanup()

    def test_classify(self):
        self.assertEqual(classify_path("a/b.PY"), "python")
        self.assertEqual(classify_path("x.cmd"), "batch")
        self.assertEqual(classify_path("x.exe"), "exe")
        with self.assertRaises(AppFolderError):
            classify_path("notes.txt")

    def test_seed_once_then_user_owned(self):
        seeds = [("Tetris", "python", "games/tetris.py", "pygame"), ("Pad", "module", "NOTEPAD", "")]
        self.assertTrue(self.store.seed_once("D-ARCADE", seeds))
        self.assertFalse(self.store.seed_once("D-ARCADE", seeds))           # never twice
        first = self.store.entries("D-ARCADE")[0]
        self.assertEqual([e["name"] for e in self.store.entries("D-ARCADE")], ["Tetris", "Pad"])
        self.assertTrue(self.store.remove("D-ARCADE", first["id"]))
        self.assertFalse(self.store.seed_once("D-ARCADE", seeds))           # removed defaults stay removed
        self.assertEqual([e["name"] for e in self.store.entries("D-ARCADE")], ["Pad"])

    def test_seed_does_not_require_files_to_exist(self):
        self.store.seed_once("D-ARCADE", [("Later", "python", "legacy/not_here_yet.py", "")])
        entry = self.store.entries("D-ARCADE")[0]
        self.assertEqual(self.store.status(entry), "missing")

    def test_add_validates_each_kind(self):
        ok = self.store.add("D-LLM", "Tetris", "python", str(self.root / "games" / "tetris.py"))
        self.assertEqual(self.store.status(ok), "ok")
        self.store.add("D-LLM", "Docs", "url", "https://example.com/docs")
        self.store.add("D-LLM", "Games dir", "folder", str(self.root / "games"))
        self.store.add("D-LLM", "Notepad", "module", "NOTEPAD")
        self.store.add("D-LLM", "Reg", "registry", "demo-app")
        for kind, target in (("url", "ftp://x"), ("url", "https://a b"), ("python", str(self.root / "nope.py")),
                             ("python", str(self.root / "games" / "run.bat")), ("folder", str(self.root / "nope")),
                             ("bogus", "x"), ("python", "")):
            with self.assertRaises(AppFolderError, msg=f"{kind} {target}"):
                self.store.add("D-LLM", "X", kind, target)
        with self.assertRaises(AppFolderError):
            self.store.add("D-LLM", "  ", "module", "NOTEPAD")
        with self.assertRaises(AppFolderError):
            self.store.add("D-LLM", "Again", "module", "notepad")           # duplicate, case-insensitive
        with self.assertRaises(AppFolderError):
            self.store.add("../evil", "X", "module", "NOTEPAD")             # container name is validated

    def test_relative_targets_resolve_against_base_dir(self):
        entry = self.store.add("D-ARCADE", "Tetris", "python", "games/tetris.py")
        self.assertEqual(self.store.resolve_path(entry), self.root / "games" / "tetris.py")

    def test_move_and_limits(self):
        a = self.store.add("D-ARCADE", "A", "module", "NOTEPAD")
        b = self.store.add("D-ARCADE", "B", "module", "FILES")
        c = self.store.add("D-ARCADE", "C", "module", "BROWSER")
        self.assertTrue(self.store.move("D-ARCADE", c["id"], -2))
        self.assertEqual([e["name"] for e in self.store.entries("D-ARCADE")], ["C", "A", "B"])
        self.assertFalse(self.store.move("D-ARCADE", c["id"], -1))          # already first
        self.assertFalse(self.store.move("D-ARCADE", "missing", 1))
        for i in range(MAX_ENTRIES - 3):
            self.store.add("D-ARCADE", f"U{i}", "url", f"https://example.com/{i}")
        with self.assertRaises(AppFolderError):
            self.store.add("D-ARCADE", "overflow", "url", "https://example.com/over")

    def test_containers_are_independent(self):
        self.store.add("D-ARCADE", "A", "module", "NOTEPAD")
        self.store.add("D-LLM", "B", "module", "NOTEPAD")
        self.assertEqual(len(self.store.entries("D-ARCADE")), 1)
        self.assertEqual(len(self.store.entries("D-LLM")), 1)

    def test_corrupt_file_is_preserved_not_overwritten(self):
        self.store.add("D-ARCADE", "A", "module", "NOTEPAD")
        self.store.path.write_text("{ not json")
        self.assertEqual(self.store.entries("D-ARCADE"), [])
        self.assertTrue(self.store.path.with_suffix(".corrupt").exists())
        self.store.add("D-ARCADE", "B", "module", "NOTEPAD")                # recovers with a fresh file
        self.assertEqual(len(self.store.entries("D-ARCADE")), 1)

    def test_atomic_save_leaves_no_temp_file(self):
        self.store.add("D-ARCADE", "A", "module", "NOTEPAD")
        self.assertFalse(self.store.path.with_suffix(".tmp").exists())
        self.assertEqual(json.loads(self.store.path.read_text())["containers"]["D-ARCADE"][0]["name"], "A")

    def test_vault_targets(self):
        vault = self.root / "unlocked-session-1" / "root"
        (vault / "Applications").mkdir(parents=True)
        (vault / "Applications" / "tool.py").write_text("print(1)")
        store = AppFolderStore(self.root / "state" / "v.json", self.root, vault_root=vault)
        stored = store.to_portable(vault / "Applications" / "tool.py")
        self.assertEqual(stored, "vault:Applications/tool.py")
        entry = store.add("D-ARCADE", "Tool", "python", stored)
        self.assertEqual(store.status(entry), "ok")
        # next login: the unlocked folder is somewhere else; the same entry still resolves
        vault2 = self.root / "unlocked-session-2" / "root"
        (vault2 / "Applications").mkdir(parents=True)
        (vault2 / "Applications" / "tool.py").write_text("print(1)")
        store2 = AppFolderStore(self.root / "state" / "v.json", self.root, vault_root=vault2)
        self.assertEqual(store2.resolve_path(store2.entries("D-ARCADE")[0]), (vault2 / "Applications" / "tool.py").resolve())
        # no vault, or an escape attempt, never resolves
        self.assertEqual(self.store.status(entry), "missing")
        evil = {"kind": "python", "target": "vault:../../etc/x.py"}
        self.assertEqual(store2.status(evil), "missing")
        with self.assertRaises(AppFolderError):
            store2.resolve_path(evil)
        # picked paths: inside app folder -> relative, elsewhere -> absolute
        self.assertEqual(store.to_portable(self.root / "games" / "tetris.py"), "games/tetris.py")

    def test_user_folders(self):
        reserved = {"KOD8", "D-ARCADE"}
        key = self.store.create_folder("  Libraries  ", reserved)
        self.assertTrue(key.startswith("grp-"))
        self.assertEqual(self.store.folders(), [{"key": key, "title": "Libraries"}])
        self.assertTrue(self.store.is_expanded(key))                        # new folders start open
        for bad in ("", "   ", "x" * 31, "libraries", "kod8", "d-arcade", "bad\x01name"):
            with self.assertRaises(AppFolderError, msg=repr(bad)):
                self.store.create_folder(bad, reserved)
        self.assertEqual(self.store.rename_folder(key, "Libs", reserved), "Libs")
        self.assertEqual(self.store.rename_folder(key, "libs", reserved), "libs")   # same folder may change case
        other = self.store.create_folder("Tools", reserved)
        with self.assertRaises(AppFolderError):
            self.store.rename_folder(other, "LIBS", reserved)
        self.store.add(key, "Notepad", "module", "NOTEPAD")
        self.store.add(key, "Docs", "url", "https://example.com")
        self.assertEqual(self.store.delete_folder(key), 2)
        self.assertEqual(self.store.entries(key), [])
        self.assertEqual([f["title"] for f in self.store.folders()], ["Tools"])
        with self.assertRaises(AppFolderError):
            self.store.delete_folder("D-ARCADE")                            # built-ins cannot be deleted
        for i in range(15):
            self.store.create_folder(f"F{i}")
        with self.assertRaises(AppFolderError):
            self.store.create_folder("one too many")

    def test_order_reconciles_and_moves(self):
        default = ["A", "B", "C", "D"]
        self.assertEqual(self.store.order(default), default)
        self.assertTrue(self.store.move_in_order("D", -2, default))
        self.assertEqual(self.store.order(default), ["A", "D", "B", "C"])
        self.assertFalse(self.store.move_in_order("A", -1, default))        # already first
        self.assertFalse(self.store.move_in_order("Z", 1, default))
        # a key that leaves (module moved into a folder) and comes back returns to its place
        self.assertEqual(self.store.order(["A", "D", "C"]), ["A", "D", "C"])
        self.assertEqual(self.store.order(default), ["A", "D", "B", "C"])
        # a brand-new key lands after its default predecessor
        self.assertEqual(self.store.order(["A", "D", "B", "NEW", "C"]), ["A", "D", "B", "NEW", "C"])

    def test_hidden_modules_and_expanded(self):
        g = self.store.create_folder("Libraries")
        self.store.add(g, "DSPACE", "module", "DSPACE LIST")
        self.store.add(g, "Arcade", "module", "D-ARCADE")
        self.store.add("D-LLM", "Eye", "module", "THE EYE")                 # built-in container: shortcut only
        self.assertEqual(self.store.hidden_modules(exclude={"D-ARCADE", "D-LLM"}), {"DSPACE LIST"})
        self.assertEqual(self.store.hidden_modules(), {"DSPACE LIST", "D-ARCADE"})
        self.assertFalse(self.store.is_expanded("D-ARCADE"))
        self.store.set_expanded("D-ARCADE", True)
        self.assertTrue(self.store.is_expanded("D-ARCADE"))
        self.store.remove(g, self.store.entries(g)[0]["id"])                # removing the shortcut un-hides it
        self.assertEqual(self.store.hidden_modules(exclude={"D-ARCADE"}), set())

    def test_seed_folder_once(self):
        mods = [("DSPACE LIST", "Network atlas"), ("FTP LIST", "FTP"), ("THE EYE", "Cameras")]
        visible = ["KOD8", "D-ARCADE", "D-LLM", "BROWSER"]
        key = self.store.seed_folder_once("lib-v1", "Libraries", mods, top_of=visible)
        self.assertIsNotNone(key)
        self.assertEqual([e["target"] for e in self.store.entries(key)], ["DSPACE LIST", "FTP LIST", "THE EYE"])
        self.assertEqual(self.store.hidden_modules(), {"DSPACE LIST", "FTP LIST", "THE EYE"})
        self.assertEqual(self.store.order([*visible, key]), [key, *visible])          # first in the sidebar
        self.assertTrue(self.store.is_expanded(key))
        self.assertIsNone(self.store.seed_folder_once("lib-v1", "Libraries", mods, top_of=visible))   # only once
        self.store.delete_folder(key)
        self.assertIsNone(self.store.seed_folder_once("lib-v1", "Libraries", mods, top_of=visible))   # not brought back
        self.assertEqual(self.store.folders(), [])

    def test_seed_folder_yields_to_the_user(self):
        mods = [("DSPACE LIST", "x"), ("FTP LIST", "y")]
        mine = self.store.create_folder("libraries")                                   # same title, own folder
        self.assertIsNone(self.store.seed_folder_once("lib-v1", "Libraries", mods))
        self.assertEqual([f["key"] for f in self.store.folders()], [mine])
        store2 = AppFolderStore(self.root / "state" / "other.json", self.root)
        g = store2.create_folder("Research")
        store2.add(g, "FTP", "module", "FTP LIST")                                     # already grouped by hand
        self.assertIsNone(store2.seed_folder_once("lib-v1", "Libraries", mods))
        self.assertEqual([f["title"] for f in store2.folders()], ["Research"])
        self.assertEqual(len(store2.entries(g)), 1)

    def test_prune_once(self):
        self.store.seed_once("D-LLM", [("NOTEPAD", "module", "NOTEPAD", "Text editor"), ("KOD8", "module", "KOD8", "")])
        mine = lambda e: e["kind"] == "module" and e["note"] == "Text editor"
        self.assertEqual(self.store.prune_once("m1", "D-LLM", mine), 1)
        self.assertEqual([e["name"] for e in self.store.entries("D-LLM")], ["KOD8"])
        self.store.add("D-LLM", "Again", "module", "NOTEPAD", "Text editor")
        self.assertEqual(self.store.prune_once("m1", "D-LLM", mine), 0)     # never runs twice
        self.assertEqual(len(self.store.entries("D-LLM")), 2)

    def test_old_file_without_layout_still_loads(self):
        self.store.path.write_text(json.dumps({"version": 1, "seeded": ["D-ARCADE"],
                                               "containers": {"D-ARCADE": [{"id": "a1", "name": "T", "kind": "module", "target": "NOTEPAD", "note": ""}]}}))
        self.assertEqual(self.store.entries("D-ARCADE")[0]["name"], "T")
        self.assertEqual(self.store.folders(), [])
        key = self.store.create_folder("New")
        self.assertEqual(self.store.entries("D-ARCADE")[0]["name"], "T")    # nothing lost when layout is added
        self.assertEqual(self.store.folders()[0]["key"], key)

    def test_launch_commands(self):
        py = self.store.add("D-ARCADE", "T", "python", str(self.root / "games" / "tetris.py"))
        cmd = self.store.build_launch(py, "PY", "linux")
        self.assertEqual(cmd["argv"], ["PY", str(self.root / "games" / "tetris.py")])
        self.assertEqual(cmd["cwd"], str(self.root / "games"))
        bat = self.store.add("D-ARCADE", "R", "batch", str(self.root / "games" / "run.bat"))
        with self.assertRaises(AppFolderError):
            self.store.build_launch(bat, "PY", "linux")
        cmd = self.store.build_launch(bat, "PY", "win32")
        self.assertTrue(cmd["new_console"])
        self.assertEqual(cmd["argv"], [str(self.root / "games" / "run.bat")])
        with self.assertRaises(AppFolderError):
            self.store.build_launch(self.store.add("D-ARCADE", "W", "url", "https://example.com"), "PY", "win32")
        (self.root / "games" / "tetris.py").unlink()
        with self.assertRaises(AppFolderError):
            self.store.build_launch(py, "PY", "linux")                      # file vanished after adding


if __name__ == "__main__":
    unittest.main()
