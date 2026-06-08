# 前言



经过队内的讨论，我和其他组员对于本次项目已经有了初步的认知和理解，并且确定了组内的分工。我们组的项目是项目实训跟踪过程的OpenClaw开放智能体。我们初步的任务是先接收所有同学的项目实训申请书，通过AI给出自动评分



# 个人任务



负责基础服务搭建，后端业务逻辑层的核心服务开发，为前端提供文件处理、用户认证等基础能力

将用户上传的申请书文件提取为纯文本，为后续AI评分提供文本输入，安全保存用户上传的申报文件，实现用户注册、登录、绘画管理功能，保护用户密码安全存储



实现功能：

- PDF 多页文本提取与拼接

- Word 段落文本提取（忽略空段落）

- 纯文本文件直接读取

- 提取失败返回错误原因

- 文件类型校验

- 目录自动创建

- 学号个实验中

- 电子签名图片上传与存储

- 登录Token生成与验证

- Token过期自动清理

- 密码修改功能



# 工作部分



## 文本提取服务



采用策略模式，根据文件扩展名选择不同的提取方式，先处理简单文本文件，再处理复杂格式（PDF、DOCX）



- 项目申报书可能是 PDF 或 Word 格式，需要统一提取文本内容供 AI 评分使用

- 使用 pypdf 库读取 PDF，python-docx 库读取 Word，成本低且效果好

- 返回元组 (文本, 错误信息)，方便调用方判断是否提取成功



```python

def extract_text(file_path: str) -> tuple[str, str | None]:

    path = Path(file_path)

    suffix = path.suffix.lower().lstrip(".")

    try:

        if suffix in {"txt", "md", "log", "csv"}:

            return path.read_text(encoding="utf-8", errors="ignore"), None

        if suffix == "pdf":

            reader = PdfReader(str(path))

            chunks: list[str] = []

            for page in reader.pages:

                chunks.append(page.extract_text() or "")

            text = "\n".join(chunks).strip()

            return text, None

        if suffix == "docx":

            doc = Document(str(path))

            chunks = [p.text for p in doc.paragraphs if p.text]

            text = "\n".join(chunks).strip()

            return text, None

        return "", "unsupported file type"

    except Exception as exc:

        return "", str(exc)

```



## 文件上传服务

使用 UUID 生成唯一文件名，避免文件名冲突，同时调用前先确保存储目录存在

- 用户上传文件可能有重名，使用 UUID 保证文件唯一性

- 使用 os.path.basename 防止路径遍历攻击

- 读取全部内容后再写入，避免内存问题

由此可以将上传文件保存到本地存储目录，返回文件时存储路径和原始文件名，进而实现文件安全保存（防止重名、防止路径遍历）、目录自动创建以及空文件检测的功能



```python

async def save_upload_file(upload_file: UploadFile) -> tuple[str, str]:

    ensure_storage_dirs()

    settings = get_settings()

    original_name = upload_file.filename or "application"

    safe_name = os.path.basename(original_name)

    file_id = uuid4().hex

    target_path = settings.application_storage_path / f"{file_id}_{safe_name}"

    content = await upload_file.read()

    if not content:

        raise ValueError("empty file")

    Path(target_path).write_bytes(content)

    return str(target_path), original_name

```



## 认证服务（用户注册/登录）



使用正则表达式验证学生学好格式（12位数字），并且检测学好格式是否合法



- re.compile() 预编译正则表达式，匹配时无需重新解析，提高性能

- ^\d{12}$ ：

  - ^ 断言字符串开始

  - \d{12} 匹配恰好 12 位数字

  - $ 断言字符串结束

- 整体匹配 12 位纯数字学号



```python

STUDENT_ID_PATTERN = re.compile(r"^\d{12}$")



def validate_student_id(student_id: str) -> str:

    sid = (student_id or "").strip()

    if not STUDENT_ID_PATTERN.match(sid):

        raise HTTPException(status_code=400, detail="student_id must be 12 digits")

    return sid

```



密码安全处理：使用 PBKDF2 算法 + SHA256，迭代 200,000 次，存储盐值（salt）和哈希值，不存储明文密码



### 用户注册

工作流程：先验证学号格式 → 检查签名文件 → 保存签名 → 创建用户



- 申报系统需要学生签名（电子签名图片）作为身份认证的一部分

- 依次校验，避免无效操作浪费资源

由此可以创建新用户，保存签名图片和密码哈希

- UploadFile.content_type 来自 HTTP 请求的 Content-Type 头（如 image/png）

- .startswith("image/") 验证是否为图片类型

- 此为客户端提供的值，结合服务端检查可过滤大部分错误上传



```python

salt = os.urandom(16).hex()

pwd_hash = _hash_password(password, salt)



user = User(

    student_id=student_id,

    password_salt=salt,

    password_hash=pwd_hash,

    signature_file_name=safe_name,

    signature_path=str(target_path),

    created_at=datetime.utcnow(),

)



db.add(user)

db.commit()

db.refresh(user)

return user

```



### 会话管理

使用 UUID 生成 64 位随机 token，同时根据 remember_me 选择不同过期时间。Token 存储哈希值，不存储明文，防止泄露，短期 token 更安全，长期 token 方便用户



- 单个 UUID hex 是 32 字符，拼接后 64 字符（320 位）

- 熵值足够大，碰撞概率极低（约 2^(-160)）

- 客户端拿到的 token 是明文，但数据库只存储哈希



```python

def create_session(db: Session, user: User, remember_me: bool) -> str:

    token = uuid4().hex + uuid4().hex

    token_hash = _sha256_hex(token)

    now = datetime.utcnow()

    expires_at = now + timedelta(days=30) if remember_me else now + timedelta(days=1)



    session = UserSession(

        user_id=user.id,

        token_hash=token_hash,

        created_at=now,

        last_used_at=now,

        expires_at=expires_at,

    )



    db.add(session)

    db.commit()

    return token

```




`token_hash = _sha256_hex(token)`

这一段代码中_sha256_hex() 对 token 进行 SHA256 哈希，存储哈希值而非明文，数据库泄露也无法直接使用 token。因此验证流程为：客户端传 token → 哈希 → 与数据库比对



`expires_at = now + timedelta(days=30) if remember_me else now + timedelta(days=1)`

这段代码中timedelta 表示时间间隔

remember_me=True → 30 天有效期（适合个人设备）

remember_me=False → 1 天有效期（适合公共设备）

而过期后 token 自动失效，需重新登录



# 总结



在本阶段中，我对我们组的项目有了初步的了解和认知，同时对分工协作有了清晰的认知，知道了以小组合作的方式如何进行协作开发。在这个阶段中，我们组完成了前后端分离的开发，对于我个人任务而言，完成了文本提取和文件上传这两个核心功能，实现类用户注册和会话管理功能，完成了项目demo的初步搭建