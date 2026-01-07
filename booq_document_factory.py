from pypdf import PdfReader
import json
import sys
import argparse
from pypdf import PdfReader, PdfWriter


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
    fields = reader.get_fields()

    print("PDF Form Fields:")
    for name, info in (fields or {}).items():
        print(name, "=>", info.get("/FT"), info.get("/V"))

    last_name = payload.get("lastName")
    first_name = payload.get("firstName")
    birth_date = payload.get("birthDate")
    pesel = payload.get("pesel")
    employer_name = payload.get("employerName")

    artifact_name = f"outputfiles/PIT2_{first_name[0]}{last_name}.pdf"

    print(f"Last Name: {last_name}")
    print(f"First Name: {first_name}")
    print(f"Birth Date: {birth_date}")
    print(f"PESEL: {pesel}")
    print(f"Employer Name: {employer_name}")

    print(f"Creating document: {artifact_name}")

    if fields:
        fields["topmostSubform[0].Page1[0].PESEL1[0]"].update({"/V": pesel})
        fields["topmostSubform[0].Page1[0].Nazwisko[0]"].update({"/V": last_name})
        fields["topmostSubform[0].Page1[0].Imie[0]"].update({"/V": first_name})
        fields["topmostSubform[0].Page1[0].Zaklad[0]"].update({"/V": employer_name})
        fields["topmostSubform[0].Page1[0].DataUrodzenia[0]"].update({"/V": birth_date})
        fields["topmostSubform[0].Page1[0].DataWypelnienia[0]"].update({"/V": "2023-10-01"})  # Example fill date

    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    writer.update_page_form_field_values(writer.pages[0], fields)
    with open(artifact_name, "wb") as output_pdf:
        writer.write(output_pdf)


create_pit2()