# test_text_processing.py

import unittest
from text_processing import remove_empty_lines, join_lines, trim_text, process_text

class TestTextProcessing(unittest.TestCase):
    def test_remove_empty_lines(self):
        text = "Line1\n\nLine2\n   \nLine3"
        expected = "Line1\nLine2\nLine3"
        self.assertEqual(remove_empty_lines(text), expected)

    def test_join_lines(self):
        # Test 1: Linie bez spacji na początku powinny zostać połączone
        text = "First line\nSecond line"
        expected = "First lineSecond line"
        self.assertEqual(join_lines(text), expected)

        # Test 2: Linia zaczynająca się od spacji – nie łączy się z poprzednią
        text = "First line\n Second line"
        expected = "First line\n Second line"
        self.assertEqual(join_lines(text), expected)

        # Test 3: Linia zaczynająca się od prefiksu (np. '#') – nie łączy się
        text = "First line\n#Comment"
        expected = "First line\n#Comment"
        self.assertEqual(join_lines(text), expected)

    def test_trim_text(self):
        # Tekst zawierający marker: linia z "#" po której następuje "return"
        text = "Line1\n#\nreturn\nLine4\nLine5"
        expected = "Line1\n#\nreturn"
        self.assertEqual(trim_text(text), expected)

        # Tekst bez markerów powinien pozostać niezmieniony
        text_no_marker = "Line1\nLine2\nLine3"
        self.assertEqual(trim_text(text_no_marker), text_no_marker)

    def test_process_text(self):
        # Łączy wszystkie funkcjonalności: przycinanie, usuwanie pierwszej linii,
        # usuwanie pustych linii oraz łączenie linii.
        text = "Header\nLine1\n\nLine2\n#\nreturn\nAnother line"
        # Po trim_text otrzymamy:
        # "Header\nLine1\n\nLine2\n#\nreturn"
        # Usunięcie pierwszej linii da: "Line1\n\nLine2\n#\nreturn"
        # Usunięcie pustych linii da: "Line1\nLine2\n#\nreturn"
        # Łączenie linii: linie "Line1" i "Line2" zostaną połączone → "Line1Line2"
        expected = "Line1Line2\n#\nreturn"
        self.assertEqual(process_text(text), expected)

if __name__ == '__main__':
    unittest.main()
