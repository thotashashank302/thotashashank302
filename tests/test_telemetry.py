"""Offline checks for the activity card: python -m unittest discover -s tests."""
import datetime
import unittest
import xml.etree.ElementTree as ET

from scripts.generate_telemetry import build_svg, monthly_trajectory, top_languages


class TelemetryTests(unittest.TestCase):
    def test_current_month_and_old_dates(self):
        today = datetime.date.today()
        calendar = {"weeks": [{"contributionDays": [
            {"date": today.isoformat(), "contributionCount": 7},
            {"date": "2000-01-01", "contributionCount": 100},
        ]}]}
        labels, values = monthly_trajectory(calendar)
        self.assertEqual(len(labels), 12)
        self.assertEqual(values[-1], 7)
        self.assertEqual(sum(values), 7)

    def test_code_volume_includes_languages_outside_top_five(self):
        ranked = top_languages({"Python": 50, "TypeScript": 30, "Shell": 20}, top_n=2)
        self.assertEqual([lang["pct"] for lang in ranked], [50, 30])
        self.assertEqual(top_languages({}), [])

    def test_xml_escaping_and_no_activity(self):
        svg = build_svg(0, 0, 0, ["JAN"] * 12, [0] * 12,
                        [{"name": "A&B <test>", "pct": 100}])
        root = ET.fromstring(svg)
        self.assertIn("A&B <test>", "".join(root.itertext()))
        self.assertNotIn("nan", svg.lower())
        self.assertNotIn("inf", svg.lower())

    def test_busiest_bar_stays_below_heading(self):
        root = ET.fromstring(build_svg(9, 232, 2, ["JAN"] * 12, [100] * 12, []))
        ns = {"s": "http://www.w3.org/2000/svg"}
        bars = [r for r in root.findall('.//s:rect', ns) if r.get("width") == "20"]
        self.assertEqual(len(bars), 12)
        self.assertTrue(all(float(r.get("y")) >= 320 for r in bars))


if __name__ == "__main__":
    unittest.main()
