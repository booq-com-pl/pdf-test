import json
import sys
import argparse
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject
from pathlib import Path
from datetime import date
import shutil
import subprocess
import tempfile
from docxtpl import DocxTemplate



def load_payload():
    parser = argparse.ArgumentParser(description="Create custom documents from JSON payload")
    parser.add_argument("payload", nargs="?", help="JSON payload string (positional) or use --payload")
    parser.add_argument("--payload", dest="payload_flag", help="JSON payload string (flag)")
    args = parser.parse_args()

    payload_str = args.payload_flag or args.payload
    if not payload_str:
        print("Error: payload missing. Provide JSON as positional arg or via --payload.")
        sys.exit(2)

    try:
        return json.loads(payload_str)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON payload: {e}")
        sys.exit(2)


payload = load_payload()

def create_pit2():
    reader = PdfReader("inputfiles/PIT2.pdf")
    fields = reader.get_fields() or {}

    print("PDF Form Fields:")
    for name, info in fields.items():
        # info is a field dictionary; /FT is field type, /V is current value
        try:
            print(name, "=>", info.get("/FT"), info.get("/V"))
        except Exception:
            print(name)

    last_name = payload.get("lastName") or ""
    first_name = payload.get("firstName") or ""
    birth_date = payload.get("birthDate") or ""
    pesel = payload.get("pesel") or ""
    employer_name = payload.get("employerName") or ""

    # Output path
    out_dir = Path("outputfiles")
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_initial = first_name[0] if first_name else "_"
    artifact_name = out_dir / f"PIT2_{safe_initial}{last_name}.pdf"

    print(f"Last Name: {last_name}")
    print(f"First Name: {first_name}")
    print(f"Birth Date: {birth_date}")
    print(f"PESEL: {pesel}")
    print(f"Employer Name: {employer_name}")
    print(f"Creating document: {artifact_name}")

    # Map of field name -> value (this is what pypdf expects)
    values = {
        "topmostSubform[0].Page1[0].PESEL1[0]": pesel,
        "topmostSubform[0].Page1[0].Nazwisko[0]": last_name,
        "topmostSubform[0].Page1[0].Imie[0]": first_name,
        "topmostSubform[0].Page1[0].Zaklad[0]": employer_name,
        "topmostSubform[0].Page1[0].DataUrodzenia[0]": birth_date,
        "topmostSubform[0].Page1[0].DataWypelnienia[0]": date.today().isoformat(),
    }

    # Build writer by cloning the source PDF so all AcroForm references stay valid.
    # Copying /AcroForm manually often results in fields not being readable in the output.
    writer = PdfWriter(clone_from=reader)

    # Ensure values are visible in many viewers.
    # If this is a hybrid XFA PDF, remove /XFA so readers prefer AcroForm.
    try:
        root = writer._root_object
        acro = root.get("/AcroForm")
        if acro:
            acro_obj = acro.get_object()
            acro_obj.update({NameObject("/NeedAppearances"): BooleanObject(True)})
            if "/XFA" in acro_obj:
                print("Warning: XFA detected in /AcroForm. Removing /XFA so AcroForm values are used.")
                del acro_obj[NameObject("/XFA")]
    except Exception as e:
        print(f"Warning: couldn't adjust AcroForm/XFA: {e}")

    # Fill values. Prefer the document-level call if available; fall back to per-page.
    try:
        writer.update_page_form_field_values(None, values, auto_regenerate=True)
    except TypeError:
        for page in writer.pages:
            writer.update_page_form_field_values(page, values)

    with open(artifact_name, "wb") as output_pdf:
        writer.write(output_pdf)


def create_docx():
    """Render a DOCX template using the current payload and convert to PDF.

    Template path: `inputfiles/PIT2_template.docx` (must exist). Output files saved
    to the same `outputfiles/` directory as the PIT2 PDF (matching artifact name).
    """
    template_path = Path("inputfiles/WORD_template.docx")
    out_dir = Path("outputfiles")
    out_dir.mkdir(parents=True, exist_ok=True)

    last_name = payload.get("lastName") or ""
    first_name = payload.get("firstName") or ""
    safe_initial = first_name[0] if first_name else "_"
    base_name = out_dir / f"WORD_{safe_initial}{last_name}"

    print(f"Rendering DOCX from template: {template_path}")
    try:
        docx_path, pdf_path = render_docx_and_convert(template_path, payload, base_name)
        print(f"Saved DOCX: {docx_path}")
        print(f"Saved PDF: {pdf_path}")
    except Exception as e:
        print(f"Error creating DOCX/PDF: {e}")



def convert_docx_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    """Convert a .docx file to PDF using headless LibreOffice and return the PDF path."""
    # Ensure LibreOffice is available
    if shutil.which("soffice") is None:
        raise FileNotFoundError(
            "LibreOffice 'soffice' not found in PATH. Install it in your environment "
            "(Ubuntu: 'sudo apt-get update && sudo apt-get install -y libreoffice'; "
            "macOS: 'brew install --cask libreoffice')."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "soffice",
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(docx_path),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed: {p.stderr or p.stdout}")

    pdf_path = out_dir / (docx_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError("PDF was not created.")
    return pdf_path


def render_docx_and_convert(template_path: Path, payload: dict, output_path: Path) -> tuple[Path, Path]:
    """Render a DOCX template with `payload` and convert to PDF.

    - `template_path` must point to an existing .docx template file.
    - `output_path` is the base path (without suffix) where .docx and .pdf will be saved.

    Returns tuple (saved_docx_path, saved_pdf_path).
    """
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    if template_path.suffix.lower() != ".docx":
        raise ValueError("template_path must be a .docx file")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        in_docx = td / "template.docx"
        rendered_docx = td / "rendered.docx"
        pdf_out_dir = td / "pdf"

        # Copy template into temp dir
        shutil.copy2(template_path, in_docx)

        # Render DOCX
        try:
            doc = DocxTemplate(str(in_docx))
            doc.render(payload)
            doc.save(str(rendered_docx))
        except Exception as e:
            raise RuntimeError(f"DOCX render failed: {e}")

        # Convert to PDF
        pdf_path = convert_docx_to_pdf(rendered_docx, pdf_out_dir)

        # Move to final destination
        target_docx = output_path.with_suffix(".docx")
        target_pdf = output_path.with_suffix(".pdf")
        shutil.copy2(rendered_docx, target_docx)
        shutil.copy2(pdf_path, target_pdf)

    return target_docx, target_pdf


create_pit2()

# After generating the PIT2 PDF, also render the DOCX and convert it to PDF
create_docx()
create_docx()
