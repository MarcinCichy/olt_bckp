# text_processing.py

def remove_empty_lines(text: str) -> str:
    """
    Usuwa puste linie lub linie zawierające tylko białe znaki.
    """
    return "\n".join(line for line in text.splitlines() if line.strip())


def join_lines(text: str) -> str:
    """
    Łączy linie, które są traktowane jako kontynuacja poprzedniej.
    Jeśli linia:
      - nie zaczyna się od spacji,
      - oraz nie zaczyna się od jednego z określonych prefiksów,
    to jest dołączana do poprzedniej linii.
    """
    prefixes = ("#", "[", "ip", "ntp", "aaa", "return", "interface", "multicast")
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        # Jeśli linia nie zaczyna się od spacji i nie ma określonych prefiksów,
        # łączymy ją z poprzednią linią
        if line and not line[0].isspace() and not line.startswith(prefixes):
            if new_lines:
                new_lines[-1] = new_lines[-1].rstrip() + line
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def trim_text(text: str) -> str:
    """
    Przycina tekst do pierwszej pary linii, w której występuje:
      - linia zawierająca tylko '#' 
      - bezpośrednio po niej linia zawierająca tylko 'return'.
    Jeśli taki układ nie wystąpi, zwraca cały tekst.
    """
    lines = text.splitlines()
    for i, (curr, next_) in enumerate(zip(lines, lines[1:])):
        if curr.strip() == "#" and next_.strip() == "return":
            return "\n".join(lines[:i + 2])
    return "\n".join(lines)


def process_text(text: str) -> str:
    """
    Przetwarza tekst wykonując następujące kroki:
      1. Przycinanie tekstu za pomocą funkcji trim_text.
      2. Usuwanie pierwszej linii.
      3. Usuwanie pustych linii za pomocą funkcji remove_empty_lines.
      4. Łączenie linii za pomocą funkcji join_lines.
    """
    # Krok 1: Przytnij tekst według markerów
    trimmed = trim_text(text)

    # Krok 2: Usuń pierwszą linię, jeśli istnieje
    lines = trimmed.splitlines()
    if lines:
        lines = lines[1:]
    no_first = "\n".join(lines)

    # Krok 3: Usuń puste linie
    no_empty = remove_empty_lines(no_first)

    # Krok 4: Połącz linie zgodnie z regułami
    joined = join_lines(no_empty)
    return joined
