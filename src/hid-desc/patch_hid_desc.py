#!/usr/bin/env python3
"""
patch_hid_desc.py
Modify Usage Page and/or top-level Usage in a HID Report Descriptor binary.
Always writes to a NEW file (original is never overwritten).

Usage examples:
    python patch_hid_desc.py control.bin --usage-page 0x0081 --usage 0x83
    python patch_hid_desc.py *.bin --usage-page 0x0081
    python patch_hid_desc.py control.bin --usage-page 0x0081 --out control_patched.bin
    python patch_hid_desc.py control.bin --usage-page 0x0081 --dry-run

Options:
    --usage-page  HEX    New Usage Page value (e.g. 0x0081)
    --usage       HEX    New top-level Usage value (e.g. 0x83)
    --all-usages         Patch ALL Usage items (default: first/top-level only)
    --out         PATH   Output file path (single-file mode only)
    --dry-run            Show what would change without writing any file
"""

import sys
import argparse
from pathlib import Path


def parse_data(data):
    val = 0
    for i, b in enumerate(data):
        val |= b << (8 * i)
    return val

def needed_size(val):
    if val == 0:      return 0
    if val <= 0xFF:   return 1
    if val <= 0xFFFF: return 2
    return 4

SIZE_CODE = {0: 0, 1: 1, 2: 2, 4: 3}

def parse_items(data):
    items = []
    i = 0
    while i < len(data):
        offset = i
        prefix = data[i]; i += 1

        if prefix == 0xFE:  # Long item
            sz = data[i]; i += 1
            tag = data[i]; i += 1
            payload = data[i:i+sz]; i += sz
            items.append({"long": True, "offset": offset, "end": i,
                           "prefix": prefix, "tag": tag, "data": payload})
            continue

        sz = [0, 1, 2, 4][prefix & 0x03]
        itype = (prefix >> 2) & 0x03
        tag   = (prefix >> 4) & 0x0F
        payload = data[i:i+sz]; i += sz

        items.append({
            "long": False, "offset": offset, "end": i,
            "prefix": prefix, "type_code": itype, "tag": tag,
            "data": payload, "value": parse_data(payload),
        })
    return items

def rebuild(data, patches):
    """patches: {offset: (new_prefix, new_data)}"""
    items = parse_items(data)
    out = bytearray()
    for item in items:
        off = item["offset"]
        if off in patches:
            np, nd = patches[off]
            out.append(np)
            out.extend(nd)
        else:
            out.extend(data[item["offset"]:item["end"]])
    return bytes(out)

def patch(input_path, new_usage_page, new_usage, all_usages, out_path, dry_run):
    data = input_path.read_bytes()
    items = parse_items(data)
    patches = {}
    usage_patched = 0

    for item in items:
        if item["long"]: continue
        tc, tag, val = item["type_code"], item["tag"], item["value"]

        # Usage Page  (Global tag=0)
        if tc == 1 and tag == 0x0 and new_usage_page is not None:
            orig_sz = len(item["data"])
            new_sz  = max(orig_sz, needed_size(new_usage_page))
            nd = new_usage_page.to_bytes(new_sz, "little") if new_sz else b""
            np = (tag << 4) | (1 << 2) | SIZE_CODE[new_sz]
            print(f"  [Usage Page] @0x{item['offset']:02X}  "
                  f"0x{val:04X} -> 0x{new_usage_page:04X}  "
                  f"({item['data'].hex()} -> {nd.hex()})")
            patches[item["offset"]] = (np, nd)

        # Usage  (Local tag=0)
        elif tc == 2 and tag == 0x0 and new_usage is not None:
            if all_usages or usage_patched == 0:
                orig_sz = len(item["data"])
                new_sz  = max(orig_sz, needed_size(new_usage))
                nd = new_usage.to_bytes(new_sz, "little") if new_sz else b""
                np = (tag << 4) | (2 << 2) | SIZE_CODE[new_sz]
                print(f"  [Usage     ] @0x{item['offset']:02X}  "
                      f"0x{val:02X} -> 0x{new_usage:02X}  "
                      f"({item['data'].hex()} -> {nd.hex()})")
                patches[item["offset"]] = (np, nd)
                usage_patched += 1

    if not patches:
        print("  (nothing to patch)")
        return

    result = rebuild(data, patches)
    print(f"\n  Original ({len(data)}B): {data.hex()}")
    print(f"  Patched  ({len(result)}B): {result.hex()}")

    if dry_run:
        print("  [dry-run] File not written.")
        return

    out_path.write_bytes(result)
    print(f"  Written -> {out_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Patch Usage Page/Usage in HID descriptor .bin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument("input", nargs="+", help="Input .bin file(s)")
    parser.add_argument("--usage-page", type=lambda x: int(x, 0),
                        metavar="HEX", help="New Usage Page (e.g. 0x0081)")
    parser.add_argument("--usage", type=lambda x: int(x, 0),
                        metavar="HEX", help="New top-level Usage (e.g. 0x83)")
    parser.add_argument("--all-usages", action="store_true",
                        help="Patch ALL Usage items (default: first only)")
    parser.add_argument("--out", metavar="PATH",
                        help="Output file (single input only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes, don't write")
    args = parser.parse_args()

    if args.usage_page is None and args.usage is None:
        parser.error("Specify at least one of --usage-page or --usage")
    if args.out and len(args.input) > 1:
        parser.error("--out can only be used with a single input file")

    for inp in args.input:
        p = Path(inp)
        if not p.exists():
            print(f"[!] Not found: {p}"); continue

        out_path = Path(args.out) if args.out else p.parent / (p.stem + "_patched" + p.suffix)

        print("=" * 60)
        print(f"Input : {p.name}")
        print(f"Output: {out_path.name}")
        print("-" * 60)
        patch(p, args.usage_page, args.usage, args.all_usages, out_path, args.dry_run)
        print()

if __name__ == "__main__":
    main()
