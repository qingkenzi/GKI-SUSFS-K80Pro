#!/usr/bin/env python3
"""Minimal mkbootimg-v4-compatible boot repacker (kernel-only swap).

Usage:
  repack_boot_v4.py <stock_boot.img> <new_kernel_Image> <out_boot.img> [--partition-size N]

Semantics mirror mkbootimg for header v3/v4 A/B images:
  [header(header_size)] pad->page, [kernel] pad->page, [ramdisk] pad->page,
  [boot signature] pad->page  (then optional trailing zero pad to partition size)

The original AVB footer / vbmeta blob is dropped on purpose: the target device
has AVB verification + dm-verity disabled (vbmeta flags=3).
"""
import struct
import sys


def page_align(x, page):
    return (x + page - 1) // page * page


def parse_header(d):
    if d[:8] != b"ANDROID!":
        raise SystemExit("not an ANDROID! boot image")
    kernel_size, ramdisk_size, os_version = struct.unpack_from("<III", d, 8)
    header_size = struct.unpack_from("<I", d, 20)[0]
    header_version = struct.unpack_from("<I", d, 40)[0]
    page_size = 2048 if header_version < 3 else 4096
    sig_size = 0
    if header_version >= 4 and header_size >= 1584:
        sig_size = struct.unpack_from("<I", d, 1580)[0]
    return {
        "kernel_size": kernel_size,
        "ramdisk_size": ramdisk_size,
        "os_version": os_version,
        "header_size": header_size,
        "header_version": header_version,
        "page_size": page_size,
        "sig_size": sig_size,
        "cmdline": d[44:44 + 1536].split(b"\x00")[0],
    }


def extract(d):
    h = parse_header(d)
    p = h["page_size"]
    off = page_align(h["header_size"], p)
    kernel = d[off:off + h["kernel_size"]]
    off = page_align(off + h["kernel_size"], p)
    ramdisk = d[off:off + h["ramdisk_size"]]
    off = page_align(off + h["ramdisk_size"], p)
    sig = d[off:off + h["sig_size"]]
    return h, kernel, ramdisk, sig


def repack(d, new_kernel, new_ramdisk=None, new_sig=None):
    h, kernel, ramdisk, sig = extract(d)
    p = h["page_size"]
    if new_ramdisk is not None:
        ramdisk = new_ramdisk
    if new_sig is not None:
        sig = new_sig
    header = bytearray(d[:h["header_size"]])
    struct.pack_into("<I", header, 8, len(new_kernel))
    struct.pack_into("<I", header, 12, len(ramdisk))
    if h["header_version"] >= 4:
        struct.pack_into("<I", header, 1580, len(sig))
    out = bytearray()
    out += header
    out += b"\x00" * (page_align(len(header), p) - len(header))
    out += new_kernel
    out += b"\x00" * (page_align(len(new_kernel), p) - len(new_kernel))
    out += ramdisk
    if ramdisk:
        out += b"\x00" * (page_align(len(ramdisk), p) - len(ramdisk))
    if sig:
        out += sig
        out += b"\x00" * (page_align(len(sig), p) - len(sig))
    return bytes(out), h


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    part_size = None
    for a in sys.argv[1:]:
        if a.startswith("--partition-size="):
            part_size = int(a.split("=", 1)[1], 0)
    if len(args) < 3:
        raise SystemExit(__doc__)
    stock, kernel_path, out_path = args[0], args[1], args[2]

    stock_data = open(stock, "rb").read()
    new_kernel = open(kernel_path, "rb").read()
    out, h = repack(stock_data, new_kernel)
    if part_size:
        if len(out) > part_size:
            raise SystemExit(f"image too large: {len(out)} > {part_size}")
        out += b"\x00" * (part_size - len(out))
    open(out_path, "wb").write(out)

    hh = parse_header(out)
    print(f"stock kernel_size = {h['kernel_size']}")
    print(f"new   kernel_size = {hh['kernel_size']} ({len(new_kernel)} bytes)")
    print(f"ramdisk_size      = {hh['ramdisk_size']}")
    print(f"header_version    = {hh['header_version']}  header_size = {hh['header_size']}")
    print(f"cmdline           = {hh['cmdline']!r}")
    print(f"output size       = {len(out)} ({len(out)/1024/1024:.1f} MiB)")


if __name__ == "__main__":
    main()
