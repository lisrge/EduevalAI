项目概述

为了追踪每一组的项目进度，因此开发了一个独立的博客系统用于每一位同学的工作日志上传。在这个迷你博客当中同学们可以上传markdown格式的工作日志，也可以查看别人的工作日志。管理员系统可以看到所有人都账户信息和查看所有博客，从而方便整体的管理



技术栈选择

后端框架：FastAPI 0.109.0

现代高性能Python Web框架，原生支持异步、API设计简洁、自动生成API文档



数据库：SQLite + SQLAlchemy 2.0.35



轻量级嵌入式数据库，无需单独安装服务器

SQLAlchemy提供ORM功能，防止SQL注入

模板引擎：Jinja2



FastAPI内置支持的模板引擎

Markdown解析：markdown 3.5.2



将用户输入的MD格式转换为HTML

认证：python-jose + hashlib



JWT token认证方式

SHA256哈希加密密码

进度汇总

完成项目需求分析和技术选型

确定使用FastAPI + SQLite + SQLAlchemy技术栈

创建项目目录结构

完成数据库模型设计（User表、Post表）

实现用户注册功能

实现用户登录功能

完成密码加密存储

实现日志发布功能（MD转HTML）

实现修改密码功能

完成前端页面（登录、注册、发布、首页）

工作情况

数据库设计

用户表

12位学号作为唯一标识符，避免重复注册。第一个注册的用户自动成为管理员。密码使用SHA256加盐哈希存储，保证安全性 。同时保存明文密码方便管理员查看（区分普通用户和管理员身份）



实现的功能：



用户基本信息存储

学号唯一性约束

管理员标识

日志表

存储MD原文和转换后的HTML，提升渲染性能。使用外键关联作者，便于查询



实现的功能：



日志内容存储

作者关联

时间记录

数据库连接配置

from sqlalchemy import create\_engine

from sqlalchemy.orm import sessionmaker

import os



DATABASE\_URL = "sqlite:///./project\_blog.db"

engine = create\_engine(DATABASE\_URL, connect\_args={"check\_same\_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



def get\_db():

&#x20;   db = SessionLocal()

&#x20;   try:

&#x20;       yield db

&#x20;   finally:

&#x20;       db.close()



\# 创建表（启动时调用）

from models import Base

Base.metadata.create\_all(bind=engine)

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

实现思路：



SQLite是嵌入式数据库，一个文件即可

需要会话工厂来创建数据库会话

需要自动建表功能

从而完成数据库连接已配置，应用启动时自动创建表

核心API接口实现

用户注册接口

创建注册接口，接收表单数据，验证合法性后创建用户



实现的功能：



学号格式验证

唯一性检查

密码加密

自动管理员分配（默认第一个注册的为管理员身份，目前已经注册好管理员）

学生注册系统执行步骤：



验证学号格式

检查学号是否已经注册

检查用户名是否存在

密码加密

判断是否为第一个注册（是否会自动成为管理员）

创建用户并保存

用户登录接口

使用FastAPI内置的OAuth2表单认证

学号作为用户名登录

验证密码正确性后返回Token

Token用于后续请求的身份验证

为已注册用户提供登录功能，便于后续操作

日志发布接口

实现思路：接收标题和内容，转换为HTML后保存到数据库



使用Form(…)获取表单参数（解决422错误）

将MD格式转换为HTML供前端直接显示

需要记录作者ID和发布时间

import markdown



@app.post("/upload")

async def upload\_post(

&#x20;   request: Request, 

&#x20;   title: str = Form(...), 

&#x20;   content: str = Form(...)

):

&#x20;   # ====== 第一步：获取当前登录用户 ======

&#x20;   current\_user = get\_current\_active\_user(request)

&#x20;   

&#x20;   # ====== 第二步：MD转HTML ======

&#x20;   md = markdown.Markdown(extensions=\['extra', 'meta'])

&#x20;   html\_content = md.convert(content)

&#x20;   

&#x20;   # ====== 第三步：创建日志并保存 ======

&#x20;   post = Post(

&#x20;       title=title, 

&#x20;       content=content, 

&#x20;       html\_content=html\_content, 

&#x20;       author\_id=current\_user.id

&#x20;   )

&#x20;   db.add(post)

&#x20;   db.commit()

&#x20;   

&#x20;   return {"message": "发布成功", "post\_id": post.id}

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

26

修改密码接口

验证旧密码后可以更新新密码，让用户可以自行修改代码



需要验证旧密码确保是本人

需要确认两次新密码输入一致

需要创建新会话更新（解决detached对象问题）

前端模板实现

登录页面

实现思路：创建表单，使用fetchAPI异步提交，保存Token到localStorage



使用异步提交避免页面刷新

保存Token到localStorage供后续请求使用

使用application/x-www-form-urlencoded格式

实现了登陆表单、异步提交以及Token保存，为用户提供了登陆界面



首页界面

实现思路：遍历日志列表，显示标题、作者、时间和内容



使用for循环遍历日志

使用|safe过滤器渲染HTML内容

实现了日志列表显示、HTML内容渲染，从而展示所有工作日志

工作总结

现阶段温成龙项目基础框架的搭建和主要功能（日志的上传提交、用户注册登录）的实现，进一步确认了下一阶段的目标：完善管理员功能、搜索功能 、用户管理界面

————————————————

版权声明：本文为CSDN博主「Mars\_forever」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。

原文链接：https://blog.csdn.net/2301\_80405405/article/details/160867125

