#!/usr/bin/env python3
"""
parse_hid_desc.py
Parse USB HID Report Descriptor binary files (USB HID 1.11 spec).

Usage:
    python parse_hid_desc.py <file.bin> [file2.bin ...]
    python parse_hid_desc.py          (parses all .bin in current dir)
"""

import sys
from pathlib import Path

# ── Item type names ──────────────────────────────────────────────────────────
ITEM_TYPE = {0: "Main  ", 1: "Global", 2: "Local ", 3: "Long  "}

MAIN_TAGS = {
    0x8: "Input",
    0x9: "Output",
    0xA: "Collection",
    0xB: "Feature",
    0xC: "End Collection",
}

GLOBAL_TAGS = {
    0x0: "Usage Page",
    0x1: "Logical Minimum",
    0x2: "Logical Maximum",
    0x3: "Physical Minimum",
    0x4: "Physical Maximum",
    0x5: "Unit Exponent",
    0x6: "Unit",
    0x7: "Report Size",
    0x8: "Report ID",
    0x9: "Report Count",
    0xA: "Push",
    0xB: "Pop",
}

LOCAL_TAGS = {
    0x0: "Usage",
    0x1: "Usage Minimum",
    0x2: "Usage Maximum",
    0x3: "Designator Index",
    0x4: "Designator Minimum",
    0x5: "Designator Maximum",
    0x7: "String Index",
    0x8: "String Minimum",
    0x9: "String Maximum",
    0xA: "Delimiter",
}

COLLECTION_TYPES = {0: "Physical", 1: "Application", 2: "Logical", 3: "Report",
                    4: "Named Array", 5: "Usage Switch", 6: "Usage Modifier"}

INPUT_OUTPUT_BITS = ["Data/Constant", "Array/Variable", "Absolute/Relative",
                     "No Wrap/Wrap", "Linear/Non-linear", "Preferred State/No Preferred",
                     "No Null/Null state", "Non-volatile/Volatile", "Bit Fields/Buffered Bytes"]

# ── Known Usage Pages ────────────────────────────────────────────────────────
USAGE_PAGES = {
    0x0001: "Generic Desktop",
    0x0002: "Simulation",
    0x0003: "VR",
    0x0004: "Sport",
    0x0005: "Game",
    0x0006: "Generic Device",
    0x0007: "Keyboard/Keypad",
    0x0008: "LED",
    0x0009: "Button",
    0x000A: "Ordinal",
    0x000B: "Telephony",
    0x000C: "Consumer",
    0x000D: "Digitizers",
    0x000F: "Physical Interface Device",
    0x0014: "Alphanumeric Display",
    0x0040: "Medical Instrument",
    0x0059: "Lighting and Illumination (LampArray)",
    0x0080: "Monitor",
    0x0081: "Monitor Enumerated Values",
    0x0082: "VESA Virtual Controls",
    0x0084: "Power Device",
    0x0085: "Battery System",
    0xFF00: "Vendor Defined (0xFF00)",
}

def usage_page_str(val):
    known = USAGE_PAGES.get(val, "")
    if not known:
        if 0xFF00 <= val <= 0xFFFF:
            known = "Vendor Defined"
        elif 0x0092 <= val <= 0xFEFF:
            known = "Reserved"
    suffix = f"  <- {known}" if known else ""
    return f"0x{val:04X}{suffix}"

def parse_data(data):
    val = 0
    for i, b in enumerate(data):
        val |= b << (8 * i)
    return val

def io_flags_str(val):
    flags = []
    for i, names in enumerate(INPUT_OUTPUT_BITS):
        pair = names.split("/")
        flags.append(pair[1 if (val >> i) & 1 else 0])
    return " | ".join(f[:3] for f in flags[:3]) + f"  (0x{val:02X})"

def parse_descriptor(data):
    items = []
    i = 0
    while i < len(data):
        prefix = data[i]; i += 1

        if prefix == 0xFE:  # Long item
            size = data[i]; i += 1
            tag  = data[i]; i += 1
            payload = data[i:i+size]; i += size
            items.append({"type": "Long", "tag": tag, "data": payload, "offset": i-size-3})
            continue

        size_code = prefix & 0x03
        itype     = (prefix >> 2) & 0x03
        tag       = (prefix >> 4) & 0x0F
        size      = [0, 1, 2, 4][size_code]
        payload   = data[i:i+size]; i += size

        items.append({
            "prefix": prefix,
            "type_code": itype,
            "tag": tag,
            "data": payload,
            "value": parse_data(payload),
            "offset": i - size - 1,
        })
    return items

def format_item(item, indent=0):
    pad = "  " * indent
    tc = item["type_code"]
    tag = item["tag"]
    val = item["value"]
    data = item["data"]
    hex_bytes = " ".join(f"{b:02X}" for b in [item["prefix"]] + list(data))

    type_str = ITEM_TYPE.get(tc, "?")

    if tc == 0:  # Main
        name = MAIN_TAGS.get(tag, f"Main(0x{tag:X})")
        if tag == 0xA:   detail = COLLECTION_TYPES.get(val, f"0x{val:02X}")
        elif tag == 0xC: detail = ""
        elif tag in (0x8, 0x9, 0xB): detail = io_flags_str(val)
        else: detail = f"0x{val:02X}"
    elif tc == 1:  # Global
        name = GLOBAL_TAGS.get(tag, f"Global(0x{tag:X})")
        if tag == 0x0:   detail = usage_page_str(val)
        elif tag in (0x1, 0x2, 0x3, 0x4): detail = str(val)
        elif tag == 0x9: detail = f"{val}  (report = {val} bytes)"
        else:            detail = f"0x{val:X}  ({val})"
    elif tc == 2:  # Local
        name = LOCAL_TAGS.get(tag, f"Local(0x{tag:X})")
        detail = f"0x{val:04X}" if val > 0xFF else f"0x{val:02X}"
    else:
        name = "Long"
        detail = data.hex()

    return f"  [{item['offset']:03X}] {hex_bytes:<20}  {type_str}  {pad}{name:<22} {detail}"

def print_descriptor(path):
    data = path.read_bytes()
    items = parse_descriptor(data)

    print("=" * 70)
    print(f"  File  : {path.name}")
    print(f"  Size  : {len(data)} bytes")
    print("=" * 70)
    print(f"  {'Offset+Hex':<22}  {'Type':<6}  {'Item':<22} Value")
    print("-" * 70)

    indent = 0
    usage_page = None
    top_usage = None
    rep_size = rep_count = None
    in_bytes = out_bytes = None

    for item in items:
        tc = item["type_code"]
        tag = item["tag"]
        val = item["value"]

        if tc == 0 and tag == 0xC:  # End Collection
            indent = max(0, indent - 1)

        print(format_item(item, indent))

        if tc == 0 and tag == 0xA:  # Collection
            indent += 1
        if tc == 1 and tag == 0x0:  usage_page = val
        if tc == 2 and tag == 0x0 and top_usage is None: top_usage = val
        if tc == 1 and tag == 0x7: rep_size = val
        if tc == 1 and tag == 0x9: rep_count = val
        if tc == 0 and tag == 0x8 and rep_size and rep_count:  # Input
            in_bytes = rep_size * rep_count // 8
        if tc == 0 and tag == 0x9 and rep_size and rep_count:  # Output
            out_bytes = rep_size * rep_count // 8

    print("-" * 70)
    print(f"  Summary:")
    print(f"    Usage Page : {usage_page_str(usage_page) if usage_page is not None else 'n/a'}")
    if top_usage is not None:
        print(f"    Top Usage  : 0x{top_usage:02X}")
    if in_bytes:  print(f"    Input      : {in_bytes} bytes/report")
    if out_bytes: print(f"    Output     : {out_bytes} bytes/report")
    print()

def main():
    if len(sys.argv) >= 2:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        paths = sorted(Path(".").glob("*.bin"))
        if not paths:
            print("No .bin files found. Usage: parse_hid_desc.py <file.bin> ...")
            sys.exit(1)

    for p in paths:
        if not p.exists():
            print(f"[!] Not found: {p}")
            continue
        print_descriptor(p)

if __name__ == "__main__":
    main()
