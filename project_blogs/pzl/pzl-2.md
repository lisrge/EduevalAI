# 个人任务简介

负责项目核心业务功能开发，包括 AI 智能评分、文件预览、数据导出等关键功能。这些功能是整个项目的价值核心，直接面向用户使用场景，实现对项目申报书的自动化AI评分。将申报文件转换为前端可预览的格式，支持 PDF 原生预览和 DOCX 转 HTML。将申报评分数据导出为常用格式，支持 CSV 和 Excel 导出

# 工作内容

## AI评分服务
评分请求构建：
定义系统提示词，明确评分维度和输出格式，主函数判断是否配置了模型，未配置时使用规则回退。系统提示词确保 AI 理解评分标准，输出结构化 JSON，支持配置化（可切换不同模型供应商），异常时自动回退到规则评分，保证服务可用
- Prompt Engineering（提示词工程） 是调教 AI 模型的核心技术
- 提示词包含：
    - 角色定义：你是项目申请书评审助手 - 让模型扮演专业评审
    - 评分维度：实用性 60 分 + 创新性 40 分 - 明确打分标准
    - 输出格式：必须包含指定字段 - 强制结构化输出
    - 特殊要求：措辞尽量多样化 - 避免重复评语
- 实用性维度细分为：需求、范围、流程、步骤、输出、前景
- 创新性维度细分为：大模型、智能体、设计、难度
  
(text or "") ；处理 None 值
.strip() ：去除首尾空白，避免空字符串判断失误

文本为空直接回退，无需调用 AI（节省成本）

```python
SYSTEM_PROMPT = """你是项目申请书评审助手。请严格根据以下标准评分，并仅返回JSON。
评分结构：
1.项目实用性60分：来自实际需求、应用范围适合、操作流程简洁、操作步骤明确、应用输出确切、具有实用前景。
2.项目创新性40分：合理使用大模型、智能体，设计合理，技术具有难度，工作量适度。
输出字段必须包含：practicality_score, innovation_score, total_score, practicality_reason, innovation_reason
要求：在不偏离事实的前提下，措辞尽量多样化，避免多次评分出现完全相同的评语。
"""

async def score_application_text(text: str | None) -> ScorePayload:
    settings = get_settings()
    normalized_text = (text or "").strip()
    if not normalized_text:
        return _fallback_score("", reason="申请书正文缺失，需人工复核。")
    if (
        settings.model_provider.lower() == "openai-compatible"
        and settings.model_base_url
        and settings.model_api_key
    ):
        try:
            return await _score_with_openai_compatible(normalized_text)
        except Exception:
            return _fallback_score(normalized_text, reason="模型调用失败，已回退到规则评分，建议人工复核。")
    return _fallback_score(normalized_text, reason="未配置模型密钥，当前使用规则评分，建议配置模型以启用AI评审。")
```

### OpenClaw兼容接口调用

使用 httpx 异步调用 OpenAI 兼容接口
- 设置 temperature=0.55 保证输出稳定性又有多样性
- 使用 response_format 强制 JSON 输出
由此可以使用httpx异步调用OpenClaw兼容接口，设置 temperature=0.55，保证输出稳定性又有多样性。使用 response_format 强制 JSON 输出

- essages 格式：OpenAI Chat API 标准格式
    - system 消息：系统提示词（全局指导）
    - user 消息：用户输入（申报书内容）
- temperature 参数：0 = 完全确定性，1 = 完全随机，0.55 平衡稳定性和多样性
- response_format：强制 JSON 输出，防止模型返回 Markdown 包裹的 JSON
- httpx：Python 异步 HTTP 客户端（类似 requests 的异步版本）
- AsyncClient 自动管理连接池，高并发下性能优异
- timeout=60.0：AI 模型响应可能很慢（涉及模型推理），60 秒足够
- async with 确保请求结束后自动关闭连接

```python
async def _score_with_openai_compatible(text: str) -> ScorePayload:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.model_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.model_name,
        "temperature": 0.55,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"申请书内容如下:\n{text}\n请直接返回JSON。"},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            settings.model_base_url.rstrip("/") + "/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
```

### 规则回退评分

使用关键词匹配计算基础分，再根据关键词命中数量加分，上限封顶

- 列表推导式遍历关键词列表
- .lower() 统一大小写（关键词和文本都转小写）
- 命中则计数 +1
- sum() 汇总命中总数

评分公式：
1. 实用性：基础分 20 + 命中数×5，上限 60
2. 创新性：基础分 12 + 命中数×4，上限 40

```python
def _fallback_score(text: str, reason: str | None = None) -> ScorePayload:
    practicality_keywords = ["需求", "应用", "流程", "步骤", "输出", "落地", "场景", "实用"]
    innovation_keywords = ["大模型", "智能体", "agent", "算法", "多模态", "自动化", "推理", "检索"]
    
    practicality_hits = sum(1 for keyword in practicality_keywords if keyword.lower() in text.lower())
    innovation_hits = sum(1 for keyword in innovation_keywords if keyword.lower() in text.lower())
    
    practicality_score = min(20 + practicality_hits * 5, 60)
    innovation_score = min(12 + innovation_hits * 4, 40)
    total_score = practicality_score + innovation_score
    
    return ScorePayload(
        practicality_score=practicality_score,
        innovation_score=innovation_score,
        total_score=total_score,
        practicality_reason=f"规则评分：命中实用关键词 {practicality_hits} 个",
        innovation_reason=f"规则评分：命中创新关键词 {innovation_hits} 个",
        needs_human_review=reason is not None
    )
```

## 文件预览服务

### DOCX转HTML
提取DOCX段落文本，拼接为HTML，使用<pre>标签保留格式

- python-docx 库内部解析 .docx 文件（本质是 ZIP 包含 XML）
- doc.paragraphs 返回所有段落对象
- p.text 获取段落文本内容
- (p.text or "") 处理 None（空段落可能返回 None）
- if text 过滤空段落（Word 中的回车会产生空段落）
- 缓存机制：检查输出文件是否存在
- st_mtime 是文件最后修改时间
- 如果 HTML 文件比 DOCX 文件新，说明之前已转换，直接返回缓存
- 避免重复转换，提升性能

```python
def _docx_to_html(input_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{input_path.stem}.html"
    if out.exists() and out.stat().st_mtime >= input_path.stat().st_mtime:
        return out
    doc = Document(str(input_path))
    lines: list[str] = []
    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            lines.append(text)
    body = "\n\n".join(lines)
    html = (
        "<!doctype html>"
        "<html>"
        "<head>"
        "<meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "<title>Application Preview</title>"
        "<style>"
        "body{font-family:Segoe UI, PingFang SC, sans-serif;margin:0;padding:20px;line-height:1.6;color:#123456}"
        "pre{white-space:pre-wrap;word-break:break-word;font-family:inherit;margin:0;}"
        "</style>"
        "</head>"
        "<body>"
        f"<pre>{escape(body)}</pre>"
        "</body>"
        "</html>"
    )
    out.write_text(html, encoding="utf-8")
    return out
```

### 预览入口函数
PDF直接返回，DOCX转化为HTML，提供统一预览入口，根据类型进行处理

- PDF是浏览器原生支持的格式
- Chrome、Edge、Firefox 内置 PDF 渲染器
- 直接返回文件路径和 application/pdf 类型
- 浏览器会显示内置 PDF 阅读器
- DOCX浏览器不支持直接显示，必须转化为HTML
- text/html; charset=utf-8 告诉浏览器这是 HTML 文档，使用 UTF-8 编码

```python
def get_preview_file(file_path: str) -> PreviewResult:
    ensure_storage_dirs()
    settings = get_settings()

    src = Path(file_path)
    if not src.exists():
        raise PreviewError("source file not found")

    suffix = src.suffix.lower().lstrip(".")
    if suffix == "pdf":
        return PreviewResult(path=str(src), media_type="application/pdf")

    if suffix == "docx":
        out_dir = settings.preview_storage_path
        html_path = _docx_to_html(src, out_dir)
        return PreviewResult(path=str(html_path), media_type="text/html; charset=utf-8")

    raise PreviewError("unsupported preview type")
```

## 数据导出服务

### CSV导出

使用标准库csv模块，utf-8-sig 编码（带 BOM，Excel 打开不乱码）

- StringIO 在内存中创建文件对象，数据存在内存中，不写入磁盘，适合小中型数据导出
- getvalue() 获取 StringIO 中的所有内容
- encode("utf-8-sig")：UTF-8 编码 + BOM (Byte Order Mark)
- BOM 是 3 字节：EF BB BF
- Excel 看到 BOM 会自动以 UTF-8 打开，否则可能以系统默认编码（GBK）打开导致乱码
- 由于csv不支持布尔类型，因此要将布尔值转化为数值True → 1，False → 0

```python
def build_csv_bytes(rows: Iterable[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "student_name", "student_id", "project_title",
        "practicality", "innovation", "total", "needs_human_review"
    ])
    for row in rows:
        writer.writerow([
            row.get("id"),
            row.get("student_name"),
            row.get("student_id"),
            row.get("project_title"),
            row.get("practicality_score"),
            row.get("innovation_score"),
            row.get("total_score"),
            1 if row.get("needs_human_review") else 0,
        ])
    return output.getvalue().encode("utf-8-sig")
```

### Excel导出

Excel格式更加规范，可支持更多数据，并且内存缓冲减少磁盘IO，因此可以使用excel格式。使用 openpyxl 库创建 Excel 文件, 写入内存缓冲区，避免生成临时文件

- Workbook 创建新的 Excel 工作簿
- active 获取当前活动工作表（默认有一个

```python
def build_xlsx_bytes(rows: Iterable[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "scores"
    ws.append([
        "id", "student_name", "student_id", "project_title",
        "practicality", "innovation", "total", "needs_human_review"
    ])
    for row in rows:
        ws.append([
            row.get("id"),
            row.get("student_name"),
            row.get("student_id"),
            row.get("project_title"),
            row.get("practicality_score"),
            row.get("innovation_score"),
            row.get("total_score"),
            1 if row.get("needs_human_review") else 0,
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

# 总结

本阶我主要完成了三项关键功能：

1.	AI 评分服务实现了项目申报书的智能评审功能。通过定义系统提示词，将评分维度量化为实用s性60分和创新性40分，并调用OpenAI兼容接口获取结构化评分结果。同时设计了规则回退机制，当AI模型不可用时，通过关键词匹配算法提供基础评分，确保服务高可用
2.	文件预览服务解决了申报文件在线查看需求。针对PDF和DOCX两种常用格式，采用差异化处理策略：PDF直接返回由浏览器原生渲染，DOCX则转换为HTML并注入CSS样式，同时加入缓存机制避免重复转换
3.	数据导出服务提供了评分结果的导出能力。实现了CSV和Excel两种格式导出，使用utf-8-sig编码解决Excel打开CSV乱码问题，内存缓冲区方式减少磁盘IO操作
本阶段工作使项目具备了AI智能评分、文件预览、数据导出等核心功能，为前端提供了完整的业务能力支撑
