---
name: seedream
description: 调用火山方舟 Seedream 5.0 生成和编辑图片：文生图、单图 / 多图参考生图、组图、联网搜索生图（lite），图层拆分、交互编辑、透明背景（pro），图片直接落盘。当用户说「用 Seedream / 豆包生图」「画一张…」「按这几张参考图融合成一张」「生成一组连贯的图 / 分镜」「把这张海报拆成图层」「在图上标记的位置加个东西」「抠成透明背景」时使用。
---

# seedream

`<SKILL_ROOT>` 指本文件所在的目录。需要环境变量 `ARK_API_KEY`（方舟控制台 → API Key 管理）。

```bash
python3 "<SKILL_ROOT>/scripts/seedream.py" gen [--model pro|lite] [--image P ...] [--size S] \
        [--format png|jpeg] [--transparent] [--layers] [--group N] [--web-search] [--fast] \
        [--watermark] [--out DIR] [--dry-run] (PROMPT | - | --prompt-file F)
```

- 输出一个 JSON：`ok`、`files`（落盘路径）、`layers`（图层拆分时的 z_index / 名称 / 边界框）、`usage`、`errors`（组图里单张失败）、`error`。
- `--image` 可重复，本地路径会自动转成 Base64，URL 原样传。默认不加水印，`--dry-run` 只校验参数、打印请求体。
- 调用是同步的，图层拆分和组图可能要一两分钟。
- 同一套功能也有 MCP 版本：`uv run --script "<SKILL_ROOT>/scripts/mcp_server.py"`，提供一个 `generate_image` 工具，参数和上面的命令行一一对应，图片默认存到 `SEEDREAM_OUT_DIR`（默认 `~/Downloads/seedream`）。客户端已经接入这个 MCP 时直接调工具，不必再跑脚本。

## 选模型

| 需求 | 模型 |
|---|---|
| 单张高质量图、多语言提示词、对时延敏感（`--fast`） | `pro`（默认，`doubao-seedream-5-0-pro-260628`） |
| 图层拆分 `--layers`、透明背景 `--transparent`、交互编辑 | 只能用 `pro` |
| 组图 `--group N`、联网搜索 `--web-search`、2K 以上（3K / 4K） | 只能用 `lite`（`doubao-seedream-5-0-260128`） |

参考图上限：pro 10 张，lite 14 张；组图要求参考图数加生成数不超过 15。不兼容的组合脚本会在本地直接报错。

## 尺寸

- 推荐只给档位，宽高比写进提示词（如「竖版 9:16 手机壁纸」），由模型决定实际像素。pro 可选 `1K` / `1.5K` / `2K`（默认 2K，1.5K 和 1K 同价、效果更好）；lite 可选 `2K` / `3K` / `4K`。
- 也可以写 `宽x高`，两种写法不能混用。总像素范围：pro 在 921600 到 4624220 之间，lite 在 3686400 到 16777216 之间；宽高比都在 1/16 到 16 之间。
- 图层拆分时 `size` 默认 `auto`，按原图尺寸输出，并夹在 1K 到 2K 之间。

## 写提示词

- 中文不超过 300 字，英文不超过 600 词，太长会丢细节。多图参考时用「图1」「图2」指明各取什么。
- **图层拆分**：可以不写提示词，模型会自动拆出主要元素；要指定拆哪些，用 0–1000 的归一化坐标框选，如 `标题文字的坐标为<bbox>180 64 812 198</bbox>，鹦鹉的坐标为<bbox>347 305 642 997</bbox>`。最多拆 16 个图层，任一图层失败整次报错。产出是底图 `layer-00` 加各图层 png，叠放顺序和位置记录在 `layers.json`（用 `bounding_box.absolute` 按 z_index 从小到大贴回底图即可还原）。
- **交互编辑**：先在原图上画框、箭头或草图标出位置，再把这张图作为 `--image` 传入，提示词里写「在左下角标记区域添加…，移除所有标记线条，保持构图不变」。
- **透明背景**：只支持传 1 张带透明通道的 png，输出也是 png。

## 注意

- 生成按成功张数计费，组图和图层拆分会一次产出多张，先确认用户要的数量。图层拆分把底图和每个图层都算一张，一张普通照片自动拆分实测就产出了 11 张。
- 失败时先看 `error`。参数取值可能随官方更新变化，以[图片生成 API 文档](https://ark.volcengine.com/region:cn-beijing/docs/ark/image-generation-api)为准；要用 Endpoint ID，直接传给 `--model`，此时脚本跳过本地的模型能力校验。
