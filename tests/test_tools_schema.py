import unittest
from core.agent import TOOLS


class TestToolsSchema(unittest.TestCase):
    def test_tools_count_and_types(self):
        self.assertGreaterEqual(len(TOOLS), 10)
        for tool in TOOLS:
            self.assertEqual(tool.get("type"), "function")
            func = tool.get("function", {})
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)

            params = func["parameters"]
            self.assertEqual(params.get("type"), "object")
            self.assertIn("properties", params)

    def test_expected_tools_present(self):
        names = {t["function"]["name"] for t in TOOLS}
        expected = {
            "web_search",
            "search_docs",
            "load_skill",
            "github_list_repos",
            "github_read_file",
            "gdrive_search_files",
            "gcalendar_list_events",
            "gmail_search_emails",
            "gtasks_list_tasks",
        }
        for name in expected:
            self.assertIn(name, names, f"Expected tool {name} not found in TOOLS schema")


if __name__ == "__main__":
    unittest.main()
