"""Keep portfolio documentation links and privacy-critical setup examples accurate."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_local_markdown_links_resolve(self):
        documents = [ROOT / "README.md", ROOT / "SECURITY.md", *sorted((ROOT / "architecture").glob("*.md"))]
        for document in documents:
            for target in re.findall(r"\]\(([^\s)]+)\)", document.read_text()):
                if target.startswith(("https://", "http://", "#", "mailto:")):
                    continue
                with self.subTest(document=document.name, target=target):
                    self.assertTrue((document.parent / target.split("#", 1)[0]).is_file())

    def test_setup_uses_private_processing_repository(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("GITHUB_REPO=your-private-processing-repository", readme)
        self.assertNotIn("GITHUB_REPO=your-public-repository", readme)

    def test_readme_discloses_incomplete_deployment_parity(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("architecture/SOURCE_STATUS.md", readme)
        self.assertIn("not yet a complete copy of the latest hosted dashboard", readme)


if __name__ == "__main__":
    unittest.main()
