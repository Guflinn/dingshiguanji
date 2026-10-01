# -*- coding: utf-8 -*-
"""从清华镜像直接下载 wheel 并解压到 pylibs，绕开 pip。"""
import html
import os
import re
import urllib.request
import zipfile
from urllib.parse import urljoin

BASE = "https://pypi.tuna.tsinghua.edu.cn/simple"
HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "pylibs")
TMP = os.path.join(HERE, ".tmp")

PACKAGES = [
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "packaging",
    "pefile",
    "pywin32-ctypes",
    "setuptools",
]

# 每个包优先选择的 wheel 特征（按顺序匹配）
PREFER = {
    "pyinstaller": ["py3-none-win_amd64"],
    "pyinstaller-hooks-contrib": ["py3-none-any"],
    "altgraph": ["py2.py3-none-any", "py3-none-any"],
    "packaging": ["py3-none-any"],
    "pefile": ["py3-none-any"],
    "pywin32-ctypes": ["py3-none-any"],
    "setuptools": ["py3-none-any"],
}


def version_key(name: str):
    m = re.search(r"-(\d+(?:\.\d+)*)(?:\.post\d+)?-", name)
    if m:
        return tuple(int(x) for x in m.group(1).split("."))
    return (0,)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "dsh-builder/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def pick_wheel(html_text: str, pkg: str, index_url: str):
    # 解析所有 .whl 链接（href 可能带 & 实体）
    wheels = re.findall(r'href="([^"]+\.whl(?:#[^"]*)?)"', html_text)
    cands = []
    for w in wheels:
        name = html.unescape(w.split("#")[0].split("/")[-1])
        if name.endswith(".whl") and not name.endswith(".data"):
            cands.append((name, urljoin(index_url, html.unescape(w.split("#")[0]))))
    if not cands:
        raise RuntimeError("%s 没有找到 wheel" % pkg)
    # 按版本号降序，取最新
    cands.sort(key=lambda c: version_key(c[0]), reverse=True)
    prefs = PREFER.get(pkg, ["py3-none-any", "py2.py3-none-any", "win_amd64"])
    # 在最新版本中按平台偏好选
    top_ver = version_key(cands[0][0])
    same_ver = [c for c in cands if version_key(c[0]) == top_ver]
    for p in prefs:
        for name, url in same_ver:
            if p in name:
                return name, url
    return same_ver[-1]


def main():
    os.makedirs(TARGET, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    for pkg in PACKAGES:
        print("==>", pkg)
        index_url = "%s/%s/" % (BASE, pkg)
        html_text = fetch(index_url).decode("utf-8", "replace")
        name, url = pick_wheel(html_text, pkg, index_url)
        print("    下载", name, "  <-", url)
        data = fetch(url)
        wheel_path = os.path.join(TMP, name)
        with open(wheel_path, "wb") as f:
            f.write(data)
        with zipfile.ZipFile(wheel_path) as z:
            z.extractall(TARGET)
        print("    解压完成", len(data), "bytes")
    print("全部完成")


if __name__ == "__main__":
    main()
