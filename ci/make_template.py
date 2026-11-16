#!/usr/bin/env python3
"""从一份「原厂 boot 分区完整 dump」提取 4 KB 打包模板（ci/boot_tpl.bin）。

模板内容 = 原厂 1584 B boot header + 原厂 AVB vbmeta 块 + AVB footer(64 B)。

用法:
  make_template.py <stock_boot_dump.img> [out=boot_tpl.bin]

要求输入是**整分区 dump**（K80 Pro 为 100663296 B = 96 MiB），因为 AVB footer
位于分区最后 64 字节。可以用:

  su -c 'dd if=/dev/block/by-name/boot_a of=/sdcard/Download/boot_stock.img bs=1M'

生成后脚本会打印 sha256，并写出 <out>.sha256；repack_boot_ci.py 会用它做完整性
校验（模板被改坏 = 打出来的 boot.img 不可启动，所以宁可直接报错）。
"""
import hashlib
import struct
import sys

HEADER_LEN = 1584          # boot header v3/v4 的 header_size
FOOTER_LEN = 64


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "boot_tpl.bin"

    d = open(src, "rb").read()
    if len(d) < 4096:
        raise SystemExit(f"输入太小: {len(d)} B，不是 boot 分区 dump")
    if d[:8] != b"ANDROID!":
        raise SystemExit("输入不是 Android boot image（magic != ANDROID!）")

    hv = struct.unpack_from("<I", d, 40)[0]
    hsize = struct.unpack_from("<I", d, 20)[0]
    if hv not in (3, 4):
        raise SystemExit(f"header_version={hv}，模板只适用于 v3/v4")
    if hsize != HEADER_LEN:
        raise SystemExit(f"header_size={hsize}，预期 {HEADER_LEN}（K80 Pro 原厂形态）")

    footer = d[-FOOTER_LEN:]
    if footer[:4] != b"AVBf":
        raise SystemExit(
            "最后 64 字节不是 AVB footer。请确认：① 输入是整分区 dump 而不是 Image/zip；"
            "② dump 没有被截断（大小应为分区大小）"
        )
    f_maj, f_min, orig_size, vb_off, vb_size = struct.unpack_from(">IIQQQ", footer, 4)
    if vb_off + vb_size > len(d):
        raise SystemExit(f"vbmeta 区间越界: offset={vb_off} size={vb_size} file={len(d)}")
    vbmeta = d[vb_off:vb_off + vb_size]
    if vbmeta[:4] != b"AVB0":
        raise SystemExit(f"vbmeta_offset={vb_off} 处不是 AVB0（原厂布局可能不同）")

    tpl = d[:HEADER_LEN] + vbmeta + footer
    open(out, "wb").write(tpl)

    h = hashlib.sha256(tpl).hexdigest()
    open(out + ".sha256", "w").write(h + "\n")

    print(f"原件      = {src} ({len(d)} B, header_v={hv})")
    print(f"footer    = ver {f_maj}.{f_min}, original_image_size={orig_size}, "
          f"vbmeta={vb_off}+{vb_size}")
    print(f"模板      = {out} ({len(tpl)} B = {HEADER_LEN} + {vb_size} + {FOOTER_LEN})")
    print(f"sha256    = {h}")
    print(f"已写出    = {out}.sha256（repack_boot_ci.py 会自动校验）")


if __name__ == "__main__":
    main()
