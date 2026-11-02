import unittest


class TestImports(unittest.TestCase):
    def test_core_package_import(self):
        import core
        self.assertTrue(hasattr(core, "run_agent"))
        self.assertTrue(hasattr(core, "cascade_call"))
        self.assertTrue(hasattr(core, "telemetry"))
        self.assertTrue(hasattr(core, "get_skills_registry"))

    def test_tools_package_import(self):
        import tools
        self.assertTrue(hasattr(tools, "web_search"))
        self.assertTrue(hasattr(tools, "search_docs"))
        self.assertTrue(hasattr(tools, "transcribe_audio_bytes"))
        self.assertTrue(hasattr(tools, "is_google_configured"))
        self.assertTrue(hasattr(tools, "github_list_repos"))

    def test_individual_tool_modules(self):
        from tools import search, rag, audio, github, google_mcp
        self.assertTrue(callable(search.web_search))
        self.assertTrue(callable(rag.search_docs))
        self.assertTrue(callable(audio.transcribe_audio_bytes))
        self.assertTrue(callable(github.github_list_repos))
        self.assertTrue(callable(google_mcp.is_google_configured))


if __name__ == "__main__":
    unittest.main()
