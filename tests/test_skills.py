import unittest
from core.skills_manager import get_skills_registry, load_skill_tool, _parse_frontmatter


class TestSkills(unittest.TestCase):
    def test_parse_frontmatter(self):
        sample = """---
name: test-skill
description: A test skill for testing
---
# Skill Body
Content goes here."""
        meta, body = _parse_frontmatter(sample)
        self.assertEqual(meta.get("name"), "test-skill")
        self.assertEqual(meta.get("description"), "A test skill for testing")
        self.assertIn("Content goes here", body)

    def test_registry_contains_default_skills(self):
        reg = get_skills_registry()
        self.assertIn("concise-accurate", reg)
        self.assertIn("time-date-awareness", reg)

        skill_info = reg["concise-accurate"]
        self.assertIn("instructions", skill_info)
        self.assertIn("description", skill_info)

    def test_load_skill_tool(self):
        res = load_skill_tool("concise-accurate")
        self.assertIn("instructions", res)
        self.assertNotIn("error", res)

        bad_res = load_skill_tool("non-existent-skill-xyz")
        self.assertEqual(bad_res.get("status"), "error")
        self.assertIn("message", bad_res)


if __name__ == "__main__":
    unittest.main()
