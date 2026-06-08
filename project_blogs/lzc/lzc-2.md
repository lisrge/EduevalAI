个人工作概述

我负责的是基础服务搭建，后端框架基础设施与底层服务开发，为整个系统提供数据持久化支持和配置管理能力



用户模型定义（学号、密码哈希、电子签名）

会话模型定义（Token哈希、过期时间）

申报模型定义（文件信息、文本提取状态）

评分结果模型定义（创新性、可行性得分）

登录注册Schema数据校验

用户资料Schema数据校验

申报数据Schema数据校验

工作部分

用户模型 与会话模型

编写思路：



User模型：存储用户的静态信息（学号、密码Hash、签名），这些信息在用户注册后相对稳定，变更频率低

UserSession模型： 存储用户的动态状态（Token、登录时间、过期时间），这些信息随每次登录而变化

这样编写的作用：



安全：密码和Token隔离，即使Session泄露也不会直接暴露密码

效率：查询当前登录状态只需查Session表，无需加载整个用户信息

可扩展：支持多设备同时登录、强制下线等功能

from \_\_future\_\_ import annotations



from datetime import datetime

from typing import Optional



from sqlalchemy import DateTime, ForeignKey, Integer, String

from sqlalchemy.orm import Mapped, mapped\_column, relationship



from app.db.base import Base

一键获取完整项目代码

python

1

2

3

4

5

6

7

8

9

代码作用：



引入future annotations允许使用前向引用（如 "UserSession"），解决循环导入问题

datetime处理时间戳

Optional表示字段可为空

SQLAlchemy ORM相关组件

User模型的使用：

class User(Base):

&#x20;   \_\_tablename\_\_ = "users"



&#x20;   id: Mapped\[int] = mapped\_column(Integer, primary\_key=True, index=True)

&#x20;   student\_id: Mapped\[str] = mapped\_column(String(12), unique=True, index=True, nullable=False)

&#x20;   password\_salt: Mapped\[str] = mapped\_column(String(64), nullable=False)

&#x20;   password\_hash: Mapped\[str] = mapped\_column(String(128), nullable=False)

&#x20;   signature\_file\_name: Mapped\[str] = mapped\_column(String(255), nullable=False)

&#x20;   signature\_path: Mapped\[str] = mapped\_column(String(800), nullable=False)

&#x20;   created\_at: Mapped\[datetime] = mapped\_column(DateTime, default=datetime.utcnow)



&#x20;   sessions: Mapped\[list\["UserSession"]] = relationship(

&#x20;       back\_populates="user",

&#x20;       cascade="all, delete-orphan",

&#x20;       passive\_deletes=True,

&#x20;   )

一键获取完整项目代码

python



1

2

3

4

5

6

7

8

9

10

11

12

13

14

15

16

作用：定义users表结构，存储用户基本信息

实现功能：



学号唯一约束（12位）

密码salt和hash分离存储

电子签名文件路径存储

与UserSession一对多关系

同时运用了Password Salt + Hash分离存储的原理：



Hash = SHA256(Salt + PlainPassword)

一键获取完整项目代码

1

优点：



即使数据库泄露，攻击者也无法直接还原密码

防止相同密码产生相同的Hash（阻止彩虹表攻击）

Salt应该是每个用户独一无二的随机值

UserSession模型的使用：

class UserSession(Base):

&#x20;   \_\_tablename\_\_ = "user\_sessions"



&#x20;   id: Mapped\[int] = mapped\_column(Integer, primary\_key=True, index=True)

&#x20;   user\_id: Mapped\[int] = mapped\_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

&#x20;   token\_hash: Mapped\[str] = mapped\_column(String(64), unique=True, index=True, nullable=False)

&#x20;   created\_at: Mapped\[datetime] = mapped\_column(DateTime, default=datetime.utcnow)

&#x20;   last\_used\_at: Mapped\[datetime] = mapped\_column(DateTime, default=datetime.utcnow)

&#x20;   expires\_at: Mapped\[Optional\[datetime]] = mapped\_column(DateTime)



&#x20;   user: Mapped\[User] = relationship(back\_populates="sessions")

一键获取完整项目代码

python



1

2

3

4

5

6

7

8

9

10

11

作用：定义 user\_sessions 表结构，管理登录状态

实现功能：



Token哈希存储（安全）

会话过期时间管理

外键关联User表

Mapped\[type ]是SQLAlchemy 2.0类型注解语法，mapped\_column()生成列定义。String(12)限制学号长度为12位，unique =True确保学号唯一。password\_salt和password\_hash分离存储增强安全性。relationship()建立一对多关系，cascade="all, delete-orphan"实现级联删除，passive\_deletes=True交给数据库外键级联处理。外键on\_delete="CASCADE"确保用户删除时相关会话一并删除。



申报模型与评分结果模型

一组学生的一个项目申报文件只会生成一个评分结果（即使后续重新评分，也是更新同一个记录），因此一条申报记录和它的AI评分结果是一对一关系：



一条申报文件对应一个评分结果

删除申报时，评分结果也应一并删除

使用uselist=False建立一对一关系

ApplicationRecord模型的使用

class ApplicationRecord(Base):

&#x20;   \_\_tablename\_\_ = "application\_records"



&#x20;   id: Mapped\[int] = mapped\_column(Integer, primary\_key=True, index=True)

&#x20;   student\_name: Mapped\[str] = mapped\_column(String(100), default="unknown")

&#x20;   student\_id: Mapped\[str] = mapped\_column(String(50), default="unknown", index=True)

&#x20;   project\_title: Mapped\[str] = mapped\_column(String(255), default="unknown")

&#x20;   file\_name: Mapped\[str] = mapped\_column(String(255), nullable=False)

&#x20;   file\_path: Mapped\[str] = mapped\_column(String(800), nullable=False)

&#x20;   file\_type: Mapped\[str] = mapped\_column(String(20), nullable=False)



&#x20;   text\_extract\_status: Mapped\[str] = mapped\_column(String(30), default="uploaded")

&#x20;   text\_content: Mapped\[Optional\[str]] = mapped\_column(Text)

&#x20;   extract\_error: Mapped\[Optional\[str]] = mapped\_column(Text)



&#x20;   score\_status: Mapped\[str] = mapped\_column(String(30), default="uploaded")

&#x20;   created\_at: Mapped\[datetime] = mapped\_column(DateTime, default=datetime.utcnow)

&#x20;   updated\_at: Mapped\[datetime] = mapped\_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



&#x20;   score\_result: Mapped\[Optional\["ScoreResult"]] = relationship(

&#x20;       back\_populates="application",

&#x20;       uselist=False,

&#x20;       cascade="all, delete-orphan",

&#x20;       passive\_deletes=True,

&#x20;   )

一键获取完整项目代码

python



1

2

3

4

5

6

7

8

9

10

11

12

13

14

15

16

17

18

19

20

21

22

23

24

25

作用：定义 application\_records 表，存储申报信息

实现功能：



学生姓名、学号、项目标题存储

申报文件信息存储

文件类型识别（pdf/docx/txt）

文本提取状态跟踪

文本内容存储（供AI评分）

ScoreResult模型的使用

作用：定义score\_results表，存储AI评分结果

实现功能：



创新性/可行性评分

总分计算

评分理由存储

人工复核标记

工作原理：



一对一关系：

uselist=False → 单对象，非列表



外键约束：

unique=True → 每个申报只有一条评分



级联删除：

ApplicationRecord删除 → ScoreResult一起删除



工作总结

本次负责基础服务搭建工作，主要包括后端框架基础设施与底层服务开发，为系统提供数据持久化支持和配置管理能力。具体围绕四个核心模块展开：用户与会话管理、申报与评分管理、数据模型定义。在这一阶段，用户模型已经基本搭建，评分系统也得以初步实现。本阶段完成的系统底层数据模型的建设有：用户模块实现安全认证与会话管理、申报模块实现文件上传与AI评分、校验模块实现接口数据安全保障，为整个系统提供了完整的数据持久化支持，确保业务逻辑 的可靠运行

————————————————

版权声明：本文为CSDN博主「Mars\_forever」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。

原文链接：https://blog.csdn.net/2301\_80405405/article/details/160806738

