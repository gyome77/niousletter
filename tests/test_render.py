import unittest
from pathlib import Path

from src.templating.render import prepare_render_data, render_newsletter


class RenderTests(unittest.TestCase):
    def test_render(self):
        data = prepare_render_data(
            newsletter={"name": "Demo", "frequency": "daily"},
            period={"start": "2025-01-01", "end": "2025-01-02"},
            recipient={"email": "alice@example.com", "name": "Alice"},
            items=[{"title": "A", "summary": "Sum", "links": ["https://example.com"]}],
            run_id=1,
            app_base_url="https://news.example.com",
            tracking_secret="secret",
            open_tracking=True,
            click_tracking=True,
        )
        template_dir = Path(__file__).resolve().parents[1] / "src" / "templating" / "templates"
        html_body, text_body = render_newsletter(
            template_dir,
            "newsletter_default.html.j2",
            "newsletter_default.txt.j2",
            data,
        )
        self.assertIn("Unsubscribe", text_body)
        self.assertIn("img", html_body)


if __name__ == "__main__":
    unittest.main()
