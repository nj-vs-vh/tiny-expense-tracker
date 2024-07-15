# generate Python class Currency from ISO4217 data
# see data at
# https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml


import argparse
import datetime
import pprint
import string
import xml
import xml.etree
import xml.etree.ElementTree
from pathlib import Path

from api.types.currency_iso4217 import CurrencyISO4217

ROOT_DIR = Path(__file__).parent.parent
ISO_4216_PY = ROOT_DIR / "api/iso4217.py"
ISO_4216_PY.write_text(
    f"""
# generated automatically by scripts/generate_iso4217.py on {datetime.datetime.now().isoformat(timespec='seconds')}
# not intended for manual editing

from api.types.currency_iso4217 import CurrencyISO4217

"""
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("list_one_xml_path")
    args = parser.parse_args()
    filename = Path(args.list_one_xml_path).resolve()
    if not filename.exists():
        raise FileNotFoundError(filename)

    currencies_raw: list[CurrencyISO4217] = []
    tree = xml.etree.ElementTree.parse(filename)
    root = tree.getroot()
    table = next(iter(root))
    for row in table:
        fields: list[str] = [c.text.strip() for c in row]  # type: ignore
        if len(fields) != 5:
            continue
        currencies_raw.append(
            CurrencyISO4217(
                code=fields[2],
                numeric_code=int(fields[3]),
                name=fields[1],
                entities=[fields[0]],
                precision=int(fields[4]) if fields[4].isnumeric() else 0,
            )
        )
    # print(currencies_raw)
    currencies_by_code: dict[str, CurrencyISO4217] = {}
    for c in currencies_raw:
        if c.code not in currencies_by_code:
            currencies_by_code[c.code] = c
        else:
            currencies_by_code[c.code].entities.extend(c.entities)

    with open(ISO_4216_PY, "a") as out:
        out.write("CURRENCIES = " + pprint.pformat(currencies_by_code, indent=4, width=100))
