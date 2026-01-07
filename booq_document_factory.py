from pypdf import PdfReader
import json
import sys

reader = PdfReader("inputfiles/PIT2.pdf")

fields = reader.get_fields()

for name, info in (fields or {}).items():
    print(name, "=>", info.get("/FT"), info.get("/V"))
    payload = json.loads(sys.argv[1])

    last_name = payload.get("lastName")
    first_name = payload.get("firstName")
    birth_date = payload.get("birthDate")
    pesel = payload.get("pesel")
    employer_name = payload.get("employerName")

    print(f"Last Name: {last_name}")
    print(f"First Name: {first_name}")
    print(f"Birth Date: {birth_date}")
    print(f"PESEL: {pesel}")
    print(f"Employer Name: {employer_name}")