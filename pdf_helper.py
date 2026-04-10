import io

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False


def extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    """
    Extracts all text from a PDF.
    Returns (text, page_count).
    """
    if not PDFPLUMBER_AVAILABLE:
        return "", 0
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages), len(pdf.pages)
    except Exception as e:
        print(f"PDF extract error: {e}")
        return "", 0


def generate_pdf(title: str, content: str) -> bytes | None:
    """
    Generates a PDF from title + content text.
    Returns PDF bytes or None on failure.
    """
    if not FPDF_AVAILABLE:
        return None
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 12, _clean(title[:80]), ln=True, fill=True)
        pdf.ln(4)

        # Content — parse markdown-ish formatting
        pdf.set_font("Helvetica", size=11)
        for line in content.split("\n"):
            clean = _clean(line)
            if not clean:
                pdf.ln(3)
                continue
            # Bold headings (lines starting with * or # or all caps short lines)
            if clean.startswith("**") and clean.endswith("**"):
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, clean.strip("*"))
                pdf.set_font("Helvetica", size=11)
            elif clean.startswith("*") and clean.endswith("*") and len(clean) < 100:
                pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 6, clean.strip("*"))
                pdf.set_font("Helvetica", size=11)
            elif clean.startswith("# "):
                pdf.set_font("Helvetica", "B", 14)
                pdf.multi_cell(0, 8, clean[2:])
                pdf.set_font("Helvetica", size=11)
            elif clean.startswith("## "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, clean[3:])
                pdf.set_font("Helvetica", size=11)
            elif clean.startswith("- ") or clean.startswith("• "):
                pdf.multi_cell(0, 6, "  " + clean)
            else:
                pdf.multi_cell(0, 6, clean)

        return bytes(pdf.output())
    except Exception as e:
        print(f"PDF generate error: {e}")
        return None


def _clean(text: str) -> str:
    """Remove characters that FPDF latin-1 can't handle."""
    return text.encode("latin-1", errors="replace").decode("latin-1")
