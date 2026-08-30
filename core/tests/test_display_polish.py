from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "display" / "src" / "styles.css"
IDLE = ROOT / "display" / "src" / "modes" / "Idle" / "IdleMode.tsx"
MEDIA = ROOT / "display" / "src" / "modes" / "Media" / "MediaMode.tsx"


class DisplayPolishTests(unittest.TestCase):
    def test_idle_has_readable_hierarchy_and_explicit_wall_layout_guard(self) -> None:
        styles = STYLES.read_text(encoding="utf-8")
        idle = IDLE.read_text(encoding="utf-8")

        self.assertIn("--idle-secondary-text", styles)
        self.assertIn("var(--text) 76%", styles)
        self.assertIn(".scene--ambient-idle .ambient-news li strong", styles)
        self.assertIn(".scene--ambient-idle .ambient-football strong", styles)
        self.assertIn("@media (min-width: 1200px) and (min-height: 800px)", styles)
        self.assertIn(".ambient-calendar { grid-template-columns: 1fr;", styles)
        self.assertIn('className="ambient-idle-stage"', idle)
        self.assertIn('className="ambient-calendar"', idle)

    def test_media_artwork_backdrop_is_conditional_and_has_clean_fallback(self) -> None:
        styles = STYLES.read_text(encoding="utf-8")
        media = MEDIA.read_text(encoding="utf-8")
        backdrop = styles.split(".media-artwork-backdrop {", 1)[1].split(
            ".media-header__status", 1
        )[0]

        self.assertIn('className="media-artwork-backdrop"', media)
        self.assertIn('className="media-artwork__fallback"', media)
        self.assertIn("{artwork ? (", media)
        self.assertIn("pointer-events: none", backdrop)
        self.assertNotIn("blur(", backdrop)


if __name__ == "__main__":
    unittest.main()
