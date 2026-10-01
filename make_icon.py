# -*- coding: utf-8 -*-
"""生成程序图标 icon.ico（电源符号 + 时钟）。"""
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角方形背景
r = 48
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=r, fill=(30, 36, 48, 255))
d.rounded_rectangle([10, 10, SIZE - 11, SIZE - 11], radius=r - 10,
                    outline=(79, 140, 255, 255), width=6)

cx = SIZE // 2
cy = SIZE // 2

# 时钟外圈
d.ellipse([cx - 78, cy - 78, cx + 78, cy + 78], outline=(232, 237, 245, 255), width=14)

# 刻度
import math
for i in range(12):
    a = math.radians(i * 30 - 90)
    x1 = cx + math.cos(a) * 64
    y1 = cy + math.sin(a) * 64
    x2 = cx + math.cos(a) * 72
    y2 = cy + math.sin(a) * 72
    d.line([x1, y1, x2, y2], fill=(232, 237, 245, 255), width=6)

# 指针
d.line([cx, cy, cx, cy - 46], fill=(79, 140, 255, 255), width=10)       # 分针
d.line([cx, cy, cx + 34, cy + 22], fill=(229, 83, 75, 255), width=10)   # 时针
d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(232, 237, 245, 255))

img.save("icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icon.ico 生成完成")
