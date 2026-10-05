# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""把 seedream.py 包成 stdio MCP server，校验、请求和落盘逻辑全部复用。

    uv run --script mcp_server.py

环境变量：ARK_API_KEY（必需）、SEEDREAM_OUT_DIR（默认 ~/Downloads/seedream）。
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).parent))
import seedream  # noqa: E402

OUT_ROOT = Path(seedream.os.environ.get("SEEDREAM_OUT_DIR", "~/Downloads/seedream")).expanduser()

mcp = MCPServer("seedream")


@mcp.tool()
def generate_image(
    prompt: str = "",
    model: str = "pro",
    images: list[str] | None = None,
    size: str | None = None,
    output_format: str | None = None,
    transparent: bool = False,
    layers: bool = False,
    group: int | None = None,
    web_search: bool = False,
    fast: bool = False,
    watermark: bool = False,
    out_dir: str | None = None,
) -> dict:
    """用火山方舟 Seedream 5.0 生成或编辑图片，结果保存到本地，返回文件路径。

    选模型：
    - model="pro"（默认）：单张高质量图；只有 pro 支持 layers（图层拆分）、transparent（透明背景）、
      fast（低时延）和交互编辑（在图上画框或箭头标出位置，再用提示词描述要改什么）。最多 10 张参考图。
    - model="lite"：只有 lite 支持 group（组图，生成 N 张相互关联的图）、web_search（联网搜索）、3K / 4K。
      最多 14 张参考图，参考图数加 group 不超过 15。
    也可以直接传完整的模型 ID 或 Endpoint ID。

    参数：
    - prompt：中文不超过 300 字。多图参考时用「图1」「图2」指明各取什么。图层拆分时可以留空自动拆，
      也可以用 0–1000 的归一化坐标框选，如「标题的坐标为<bbox>180 64 812 198</bbox>」。
    - images：参考图，本地绝对路径或 URL。layers、transparent 只能传 1 张（transparent 要求带透明通道的 png）。
    - size：推荐只给档位，宽高比写进 prompt。pro 可选 1K / 1.5K / 2K（默认 2K），lite 可选 2K / 3K / 4K；
      也可以写 宽x高。图层拆分默认 auto。
    - output_format：png 或 jpeg。

    按成功生成的张数计费：组图和图层拆分会一次产出多张（一张照片自动拆分实测产出 11 张），调用前先和用户确认。
    同步调用，组图或图层拆分要一两分钟。
    """
    a = SimpleNamespace(
        prompt=prompt or None, prompt_file=None, model=model, image=images or [], size=size,
        format=output_format, transparent=transparent, layers=layers, group=group,
        web_search=web_search, fast=fast, watermark=watermark, timeout=300, dry_run=False,
        out=out_dir or str(OUT_ROOT / time.strftime("%Y%m%d-%H%M%S")),
    )
    try:
        return seedream.cmd_gen(a)
    except SystemExit as e:  # encode_image 对坏参考图直接退出，这里转成普通错误
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
