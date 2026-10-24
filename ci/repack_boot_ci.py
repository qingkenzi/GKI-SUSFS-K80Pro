#!/usr/bin/env python3
"""CI 用 boot 打包器：用 4KB 模板 + 新 kernel 生成 96MB boot.img。

模板格式 (ci/boot_tpl.bin, 由 `make_template.py` 从原厂 boot 提取)：
  [0 : 1584]                     原厂 boot header（header_version=4, kernel_size 会被重写）
  [1584 : 1584+vbmeta_size]      原厂 AVB vbmeta blob（原样搬运）
  [-64 :]                        AVB footer（magiskboot 语义：original_image_size / vbmeta_offset 重算为新布局）

输出布局（与 magiskboot repack 逐字节等价，已用实机验证过）：
  header(pad->4096) | kernel(pad->4096) | vbmeta blob | 0 填充 | footer(64B)

用法: repack_boot_ci.py <boot_tpl.bin> <Image> <out.img> [--partition-size=100663296]
"""
import struct
import sys

PAGE = 4096


def align(x, p=PAGE):
    return (x + p - 1) // p * p


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    part = 100663296
    for a in sys.argv[1:]:
        if a.startswith("--partition-size="):
            part = int(a.split("=", 1)[1], 0)
    if len(args) < 3:
        raise SystemExit(__doc__)
    tpl_path, img_path, out_path = args

    tpl = open(tpl_path, "rb").read()
    kernel = open(img_path, "rb").read()

    header = bytearray(tpl[:1584])
    if header[:8] != b"ANDROID!":
        raise SystemExit("模板 header magic 异常")
    footer = tpl[-64:]
    if footer[:4] != b"AVBf":
        raise SystemExit("模板 footer magic 异常")
    f_maj, f_min, _o, _vo, vsize = struct.unpack_from(">IIQQQ", footer, 4)
    vbmeta = tpl[1584:1584 + vsize]
    if len(vbmeta) != vsize:
        raise SystemExit(f"模板里的 vbmeta 长度不符: {len(vbmeta)} != {vsize}")

    # 重写 header 的 kernel_size / ramdisk_size / signature_size
    struct.pack_into("<I", header, 8, len(kernel))
    struct.pack_into("<I", header, 12, 0)
    if struct.unpack_from("<I", header, 20)[0] >= 1584:
        struct.pack_into("<I", header, 1580, 0)

    out = bytearray(header)
    out += b"\x00" * (align(len(out)) - len(out))
    out += kernel
    out += b"\x00" * (align(len(out)) - len(out))
    avb_off = len(out)
    out += vbmeta

    new_footer = bytearray(64)
    new_footer[0:4] = b"AVBf"
    struct.pack_into(">IIQQQ", new_footer, 4, f_maj, f_min, avb_off, avb_off, vsize)

    if len(out) > part - 64:
        raise SystemExit(f"内核过大: 需要 {len(out) + 64} 字节，分区只有 {part}")
    out += b"\x00" * (part - 64 - len(out))
    out += new_footer

    open(out_path, "wb").write(out)

    hv = struct.unpack_from("<I", header, 40)[0]
    print(f"kernel_size   = {len(kernel)}")
    print(f"avb_offset    = {avb_off}  (vbmeta {vsize} B)")
    print(f"header_version= {hv}")
    print(f"output        = {len(out)} bytes")


if __name__ == "__main__":
    main()
