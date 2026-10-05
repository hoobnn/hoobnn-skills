#!/usr/bin/env python3
"""调用火山方舟 Seedream 5.0（pro / lite）生成图片，并把结果落盘。

    seedream.py gen [--model pro|lite|<模型或 Endpoint ID>] [--image PATH_OR_URL ...]
                    [--size 2K|WxH] [--format png|jpeg] [--transparent] [--layers]
                    [--group N] [--web-search] [--fast] [--watermark]
                    [--out DIR] [--timeout SEC] [--dry-run] (PROMPT | - | --prompt-file F)

stdout 只打印一个 JSON：{ok, model, files, layers, usage, errors, error, out_dir}。
以 b64_json 取回图片直接写盘，不依赖 24 小时过期的 URL。只依赖 Python 3 标准库。
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
MODELS = {
    "pro": "doubao-seedream-5-0-pro-260628",
    "lite": "doubao-seedream-5-0-260128",
}
MAX_REF = {"pro": 10, "lite": 14}
IMAGE_EXT = {"png", "jpeg", "jpg", "webp", "bmp", "tiff", "tif", "gif", "heic", "heif"}


def family(model):
    if model == MODELS["pro"] or "seedream-5-0-pro" in model:
        return "pro"
    if model == MODELS["lite"] or "seedream-5-0-26" in model:
        return "lite"
    return None  # Endpoint ID 等无法识别的，跳过本地校验，交给服务端


def encode_image(src):
    if src.startswith(("http://", "https://", "data:")):
        return src
    p = Path(src).expanduser()
    if not p.is_file():
        raise SystemExit(f"参考图不存在：{src}")
    ext = p.suffix.lower().lstrip(".")
    if ext not in IMAGE_EXT:
        raise SystemExit(f"不支持的图片格式：{p.name}")
    if p.stat().st_size > 30 * 1024 * 1024:
        raise SystemExit(f"参考图超过 30MB：{p.name}")
    mime = {"jpg": "jpeg", "tif": "tiff"}.get(ext, ext)
    return f"data:image/{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def check(a, fam):
    """服务端也会拒，但本地先挡掉，省一次请求和一份等待。"""
    n = len(a.image)
    if fam == "pro":
        if a.group or a.web_search:
            return "Seedream 5.0 pro 不支持组图（--group）和联网搜索（--web-search），改用 --model lite"
    if fam == "lite":
        if a.layers or a.transparent:
            return "图层拆分（--layers）和透明背景（--transparent）只有 Seedream 5.0 pro 支持"
        if a.fast:
            return "--fast 只有 Seedream 5.0 pro 支持"
    if fam and n > MAX_REF[fam]:
        return f"{fam} 最多 {MAX_REF[fam]} 张参考图，当前 {n} 张"
    if a.layers and n != 1:
        return "图层拆分必须且只能传 1 张图（png / jpeg）"
    if a.transparent:
        if n != 1:
            return "透明背景只支持图生图，且只能传 1 张带透明通道的图"
        if a.format == "jpeg":
            return "透明背景输出是 png，不能同时指定 --format jpeg"
    if a.group and (a.group < 1 or n + a.group > 15):
        return f"组图要求 参考图数 + 生成数 ≤ 15（当前 {n} + {a.group}）"
    if not a.prompt and not a.layers:
        return "缺少提示词（只有图层拆分可以不写）"
    return None


def build_body(a, model):
    body = {"model": model, "response_format": "b64_json", "watermark": a.watermark}
    if a.prompt:
        body["prompt"] = a.prompt
    if a.image:
        imgs = [encode_image(s) for s in a.image]
        body["image"] = imgs[0] if len(imgs) == 1 else imgs
    if a.size:
        body["size"] = a.size
    if a.format:
        body["output_format"] = a.format
    if a.transparent:
        body["background"] = "transparent"
    if a.layers:
        body["layer_decomposition"] = True
    if a.group:
        body["sequential_image_generation"] = "auto"
        body["sequential_image_generation_options"] = {"max_images": a.group}
    if a.web_search:
        body["tools"] = [{"type": "web_search"}]
    if a.fast:
        body["optimize_prompt_options"] = {"mode": "fast"}
    return body


def post(body, timeout):
    key = os.environ.get("ARK_API_KEY")
    if not key:
        return None, "未设置环境变量 ARK_API_KEY"
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/images/generations",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            err = json.loads(raw).get("error") or {}
            return None, f"HTTP {e.code} {err.get('code', '')}: {err.get('message', raw)}".strip()
        except (json.JSONDecodeError, AttributeError):
            return None, f"HTTP {e.code}: {raw[:500]}"
    except (urllib.error.URLError, TimeoutError) as e:
        return None, f"请求失败：{e}"


def save(resp, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    files, layers, errors = [], [], []
    for i, d in enumerate(resp.get("data") or []):
        if d.get("error"):
            errors.append({"index": i, **d["error"]})
            continue
        ext = "jpg" if d.get("output_format") == "jpeg" else d.get("output_format") or "png"
        z = d.get("z_index")
        name = f"layer-{z:02d}.{ext}" if z is not None else f"image-{i + 1:02d}.{ext}"
        path = out_dir / name
        if d.get("b64_json"):
            path.write_bytes(base64.b64decode(d["b64_json"]))
        elif d.get("url"):
            urllib.request.urlretrieve(d["url"], path)
        else:
            continue
        files.append(str(path))
        if z is not None:
            layers.append({k: d.get(k) for k in ("z_index", "name", "description", "size", "bounding_box")}
                          | {"file": str(path)})
    if layers:
        (out_dir / "layers.json").write_text(json.dumps(layers, ensure_ascii=False, indent=2))
    return files, layers, errors


def cmd_gen(a):
    if a.prompt == "-":
        a.prompt = sys.stdin.read()
    elif a.prompt_file:
        a.prompt = Path(a.prompt_file).read_text()
    model = MODELS.get(a.model, a.model)
    result = {"ok": False, "model": model, "files": [], "layers": [], "usage": None,
              "errors": [], "error": None, "out_dir": None}

    err = check(a, family(model))
    if err:
        result["error"] = err
        return result
    body = build_body(a, model)
    if a.dry_run:
        shown = dict(body)
        if "image" in shown:
            cut = lambda s: s[:60] + "…" if s.startswith("data:") else s  # noqa: E731
            shown["image"] = [cut(s) for s in shown["image"]] if isinstance(shown["image"], list) else cut(shown["image"])
        result.update(ok=True, request=shown)
        return result

    resp, err = post(body, a.timeout)
    if err:
        result["error"] = err
        return result
    if resp.get("error"):
        result["error"] = f"{resp['error'].get('code')}: {resp['error'].get('message')}"
        return result
    out_dir = Path(a.out or f"seedream-out/{time.strftime('%Y%m%d-%H%M%S')}").expanduser()
    files, layers, errors = save(resp, out_dir)
    result.update(ok=bool(files), files=files, layers=layers, errors=errors,
                  usage=resp.get("usage"), out_dir=str(out_dir))
    if not files:
        result["error"] = "没有生成任何图片"
    return result


def main():
    ap = argparse.ArgumentParser(description="Seedream 5.0 图片生成")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("prompt", nargs="?", help="提示词；- 表示从 stdin 读")
    g.add_argument("--prompt-file")
    g.add_argument("--model", default="pro", help="pro / lite，或完整的模型 ID、Endpoint ID")
    g.add_argument("--image", action="append", default=[], help="参考图，本地路径或 URL，可重复")
    g.add_argument("--size", help="1K / 1.5K / 2K / 3K / 4K / auto，或 宽x高")
    g.add_argument("--format", choices=["png", "jpeg"])
    g.add_argument("--transparent", action="store_true", help="透明背景（pro，单张带透明通道的输入图）")
    g.add_argument("--layers", action="store_true", help="图层拆分（pro，单张输入图）")
    g.add_argument("--group", type=int, help="组图，最多生成 N 张（lite）")
    g.add_argument("--web-search", action="store_true", help="联网搜索（lite）")
    g.add_argument("--fast", action="store_true", help="提示词优化用 fast 模式（pro）")
    g.add_argument("--watermark", action="store_true", help="加「AI 生成」水印，默认不加")
    g.add_argument("--out", help="输出目录，默认 ./seedream-out/<时间戳>")
    g.add_argument("--timeout", type=int, default=300)
    g.add_argument("--dry-run", action="store_true", help="只校验并打印请求体，不调用")
    a = ap.parse_args()
    r = cmd_gen(a)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
