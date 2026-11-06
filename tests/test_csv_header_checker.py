"""Tests for csv_header_checker — standard library unittest only."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import csv_header_checker  # noqa: E402


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    return path


def run_cli(*args, cwd=None):
    argv = [sys.executable, str(SRC / "csv_header_checker.py"), *args]
    return subprocess.run(
        argv, capture_output=True, text=True, cwd=cwd or ROOT
    )


class TestCheckFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def check(self, text, required=None):
        path = write(self.tmp.name, "a.csv", text)
        return csv_header_checker.check_file(path, required or [])

    def test_clean_file(self):
        self.assertEqual(
            self.check("id,name,price\n1,apple,0.50\n"), []
        )

    def test_header_only_file_is_clean(self):
        self.assertEqual(self.check("id,name\n"), [])

    def test_empty_name(self):
        problems = self.check("id,,price\n1,apple,0.50\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("column 2 has an empty name", problems[0])
        self.assertIn(":1:", problems[0])

    def test_leading_space(self):
        problems = self.check("id, name ,price\n1,apple,0.50\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("leading or trailing spaces", problems[0])
        self.assertIn("' name '", problems[0])

    def test_trailing_space(self):
        problems = self.check("id,name ,price\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("'name '", problems[0])

    def test_duplicate_name(self):
        problems = self.check("id,name,id\n1,apple,2\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("duplicate column name 'id'", problems[0])

    def test_duplicate_after_stripping(self):
        # "id" and " id " are the same name once spaces are trimmed.
        problems = self.check("id, id\n1,2\n")
        self.assertIn("duplicate column name 'id'", "\n".join(problems))

    def test_required_present(self):
        self.assertEqual(
            self.check("id,name\n1,apple\n", required=["name"]), []
        )

    def test_required_missing(self):
        problems = self.check("id,name\n1,apple\n", required=["price"])
        self.assertEqual(len(problems), 1)
        self.assertIn("required column 'price' is missing", problems[0])

    def test_required_matches_stripped_name(self):
        # --require matches the name after trimming spaces, so the
        # only problem is the spaces themselves.
        problems = self.check("id, name\n1,apple\n", required=["name"])
        self.assertEqual(len(problems), 1)
        self.assertIn("leading or trailing spaces", problems[0])
        self.assertNotIn("required", problems[0])

    def test_row_too_few_fields(self):
        problems = self.check("id,name,price\n1,apple\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("row has 2 field(s), header has 3", problems[0])
        self.assertIn(":2:", problems[0])

    def test_row_too_many_fields(self):
        problems = self.check("id,name\n1,apple,extra\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("row has 3 field(s), header has 2", problems[0])

    def test_blank_lines_skipped(self):
        self.assertEqual(
            self.check("id,name\n\n1,apple\n\n"), []
        )

    def test_blank_lines_before_header(self):
        problems = self.check("\n\nid,name\n1,apple\n")
        self.assertEqual(problems, [])

    def test_quoted_field_with_comma(self):
        self.assertEqual(
            self.check('id,note\n1,"hello, world"\n'), []
        )

    def test_quoted_field_with_newline_line_numbers(self):
        # A quoted field spanning two lines: the next bad row is on
        # physical line 4, and the line number must say so.
        text = 'id,note\n1,"line one\nline two"\n2,extra,fields\n'
        problems = self.check(text)
        self.assertEqual(len(problems), 1)
        self.assertIn(":4:", problems[0])
        self.assertIn("row has 3 field(s), header has 2", problems[0])

    def test_empty_file(self):
        problems = self.check("")
        self.assertEqual(len(problems), 1)
        self.assertIn("file is empty", problems[0])

    def test_only_blank_lines(self):
        problems = self.check("\n\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("file has no header row", problems[0])

    def test_missing_file(self):
        problems = csv_header_checker.check_file(
            Path(self.tmp.name) / "nope.csv", []
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("nope.csv", problems[0])

    def test_non_utf8_file(self):
        path = Path(self.tmp.name) / "bad.csv"
        path.write_bytes(b"id,name\n1,\xff\xfe\n")
        problems = csv_header_checker.check_file(path, [])
        self.assertEqual(len(problems), 1)
        self.assertIn("UTF-8", problems[0])


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_single_file(self):
        path = write(self.tmp.name, "a.csv", "id\n1\n")
        files, problems = csv_header_checker.collect(
            [str(path)], True, []
        )
        self.assertEqual(files, [path])
        self.assertEqual(problems, [])

    def test_folder_recursive(self):
        write(self.tmp.name, "a.csv", "id\n1\n")
        write(self.tmp.name, "sub/b.csv", "id\n1\n")
        write(self.tmp.name, "sub/c.txt", "not csv\n")
        files, problems = csv_header_checker.collect(
            [self.tmp.name], True, []
        )
        self.assertEqual(len(files), 2)
        self.assertEqual(problems, [])

    def test_folder_no_recursive(self):
        write(self.tmp.name, "a.csv", "id\n1\n")
        write(self.tmp.name, "sub/b.csv", "id\n1\n")
        files, _ = csv_header_checker.collect(
            [self.tmp.name], False, []
        )
        self.assertEqual(len(files), 1)

    def test_git_folder_skipped(self):
        write(self.tmp.name, "a.csv", "id\n1\n")
        write(self.tmp.name, ".git/hooks/x.csv", "id\n1\n")
        files, _ = csv_header_checker.collect(
            [self.tmp.name], True, []
        )
        self.assertEqual(len(files), 1)

    def test_exclude_pattern(self):
        write(self.tmp.name, "a.csv", "id\n1\n")
        write(self.tmp.name, "skip.csv", "id\n1\n")
        files, _ = csv_header_checker.collect(
            [self.tmp.name], True, ["skip.csv"]
        )
        self.assertEqual([f.name for f in files], ["a.csv"])

    def test_missing_path(self):
        files, problems = csv_header_checker.collect(
            [str(Path(self.tmp.name) / "nope.csv")], True, []
        )
        self.assertEqual(files, [])
        self.assertEqual(len(problems), 1)
        self.assertIn("no such file or folder", problems[0])


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_clean_exit_0(self):
        path = write(self.tmp.name, "a.csv", "id,name\n1,apple\n")
        result = run_cli(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK — 1 file(s) checked", result.stdout)
        self.assertIn("headers are clean", result.stdout)

    def test_bad_exit_1(self):
        path = write(self.tmp.name, "a.csv", "id,id\n1,2\n")
        result = run_cli(str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)
        self.assertIn("duplicate column name 'id'", result.stdout)

    def test_no_args_exit_2(self):
        result = run_cli()
        self.assertEqual(result.returncode, 2)

    def test_bad_flag_exit_2(self):
        result = run_cli("--nope")
        self.assertEqual(result.returncode, 2)

    def test_version(self):
        result = run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)

    def test_json_output(self):
        path = write(self.tmp.name, "a.csv", "id,id\n1,2\n")
        result = run_cli(str(path), "--json")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["checked"], 1)
        self.assertEqual(payload["summary"]["problems"], 1)
        self.assertIn("duplicate column name 'id'",
                      payload["files"][0]["problems"][0])
        # The summary line goes to stderr, stdout stays clean JSON.
        self.assertIn("Checked 1 file(s)", result.stderr)

    def test_json_clean(self):
        path = write(self.tmp.name, "a.csv", "id,name\n1,apple\n")
        result = run_cli(str(path), "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 0)

    def test_require_flag(self):
        path = write(self.tmp.name, "a.csv", "id,name\n1,apple\n")
        result = run_cli(str(path), "--require", "price")
        self.assertEqual(result.returncode, 1)
        self.assertIn("required column 'price' is missing",
                      result.stdout)

    def test_input_files_unchanged(self):
        text = "id,id\n1,2\n"
        path = write(self.tmp.name, "a.csv", text)
        run_cli(str(path))
        self.assertEqual(path.read_text(), text)

    def test_folder_argument(self):
        write(self.tmp.name, "a.csv", "id\n1\n")
        write(self.tmp.name, "b.csv", "id,id\n1,2\n")
        result = run_cli(self.tmp.name)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checked 2 file(s)", result.stdout)


class TestExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        expected = (ROOT / "examples" / "sample-output.txt").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quoted_outputs(self):
        readme = (ROOT / "README.md").read_text()
        good = run_cli("examples/good.csv")
        self.assertEqual(good.returncode, 0)
        self.assertIn(
            "OK — 1 file(s) checked, headers are clean.", readme
        )
        bad = run_cli("examples/bad-headers.csv")
        self.assertEqual(bad.returncode, 1)
        for line in bad.stdout.strip().splitlines():
            self.assertIn(line, readme)
        width = run_cli("examples/wrong-width.csv")
        self.assertEqual(width.returncode, 1)
        for line in width.stdout.strip().splitlines():
            self.assertIn(line, readme)
        missing = run_cli(
            "examples/missing-required.csv", "--require", "price"
        )
        self.assertEqual(missing.returncode, 1)
        for line in missing.stdout.strip().splitlines():
            self.assertIn(line, readme)


class TestHygiene(unittest.TestCase):
    def test_stdlib_only(self):
        import ast

        allowed = {
            "argparse", "csv", "fnmatch", "json", "sys", "pathlib",
        }
        test_allowed = allowed | {
            "ast", "subprocess", "tempfile", "unittest",
            "csv_header_checker",  # the module under test
        }
        for path, names in [
            (SRC / "csv_header_checker.py", allowed),
            (HERE / "test_csv_header_checker.py", test_allowed),
        ]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split(".")[0], names)
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module.split(".")[0], names)

    def test_no_placeholder_or_secrets(self):
        banned = ["TODO", "FIXME", "coming soon", "lorem",
                  "API_KEY", "api_key", "password="]
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if HERE in path.parents:
                continue  # the test file's own word lists
            if path.suffix == ".pyc":
                continue
            text = path.read_text(errors="ignore")
            for word in banned:
                self.assertNotIn(
                    word, text, f"{word} found in {path}"
                )

    def test_no_absolute_paths(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if HERE in path.parents:
                continue  # the test file's own "/tmp/" literals
            if path.suffix in {".pyc", ".csv"}:
                continue
            text = path.read_text(errors="ignore")
            self.assertNotIn("/home/", text, f"absolute path in {path}")
            self.assertNotIn("/tmp/", text, f"absolute path in {path}")

    def test_gitignore_has_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_fake_git_hooks_todo_does_not_break_scan(self):
        # The Day 21 lesson: a scan that walks .git hits GitHub's own
        # sample hooks containing "TODO". Our scans exclude .git.
        with tempfile.TemporaryDirectory() as tmp:
            hooks = Path(tmp) / ".git" / "hooks"
            hooks.mkdir(parents=True)
            (hooks / "sendemail-validate.sample").write_text(
                "# TODO: fix this\n"
            )
            found = []
            for path in Path(tmp).rglob("*"):
                if not path.is_file():
                    continue
                if ".git" in path.parts or "__pycache__" in path.parts:
                    continue
                if "TODO" in path.read_text(errors="ignore"):
                    found.append(path)
            self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
