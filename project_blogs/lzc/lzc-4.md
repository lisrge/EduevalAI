一、进度汇报

该阶段完成目标如下：



实现管理员后台界面

实现查看用户列表和密码

实现日志删除功能

实现用户搜索功能

实现用户搜索功能

实现退出登录功能

二、管理员功能概述

管理员在系统中能够看到所有用户的账号信息（学号、用户名、密码、发布的日志），有且仅有一个管理员账号能对该系统进行管理



管理员权限设置

第一个注册的用户自动成为管理员



简化管理员创建流程

无需手动配置

第一个用户就是系统管理员

从而实现了管理员的自动分配

系统中，第一个注册的用户自动成为管理员。通过is\_admin字段标识：



is\_admin = True if db.query(User).count() == 0 else False

一键获取完整项目代码

python

1

管理员ID生成

需要区别于普通学号登录

管理员使用专用的admin\_id登录

自动生成6位数字ID

从而为管理员提供专属登陆凭证

为管理员生成6位数字ID：



def generate\_admin\_id() -> str:

&#x20;   import random

&#x20;   return ''.join(\[str(random.randint(0, 9)) for \_ in range(6)])

一键获取完整项目代码

python

1

2

3

三、管理员权限验证

创建管理员页面，检查用户是否为管理员，返回用户列表和日志列表



需要验证管理员权限

需要查询所有用户、日志

需要统计每个用户的日志数量

需要获取明文密码（使用字典解决SQLAlchemy映射问题）

实现的功能：



管理员权限验证

用户列表查询

日志列表查询

统计数据

密码获取

四、用户密码管理实现

实现思路：在User表中添加plain\_password字段



hashed\_password用于登录验证（安全）

plain\_password用于管理员查看（方便）

实现明文密码的存储，便于管理员查看用户密码

注册时保存明文密码

注册时同时保存哈希密码和明文密码



哈希密码用于登录

明文密码方便管理员查看

在register接口中：



user = User(

&#x20;   student\_id=student\_id, 

&#x20;   username=username, 

&#x20;   hashed\_password=hashed\_password, 

&#x20;   plain\_password=password,  # 保存明文密码

&#x20;   is\_admin=is\_admin,

&#x20;   admin\_id=admin\_id

)

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

修改密码时更新明文

修改密码时同步更新哈希和明文

两处需要保持一致性，管理员需要看到最新的明文密码，确保密码的一致性



五、日志删除功能

删除API接口

提供DELETE接口，验证权限后删除日志



作者可以删除自己的日志

管理员可以删除任何日志

普通用户不能删除他人日志

实现的功能：



日志删除

权限验证

@app.delete("/post/{post\_id}")

async def delete\_post(request: Request, post\_id: int):

&#x20;   current\_user = get\_current\_active\_user(request)

&#x20;   

&#x20;   db = SessionLocal()

&#x20;   try:

&#x20;       post = db.query(Post).filter(Post.id == post\_id).first()

&#x20;       

&#x20;       if not post:

&#x20;           raise HTTPException(status\_code=404, detail="文章不存在")

&#x20;       

&#x20;       # ====== 验证权限：作者本人或管理员可删除 ======

&#x20;       if post.author\_id != current\_user.id and not current\_user.is\_admin:

&#x20;           raise HTTPException(status\_code=403, detail="无权限删除")

&#x20;       

&#x20;       db.delete(post)

&#x20;       db.commit()

&#x20;       

&#x20;       return {"message": "删除成功"}

&#x20;   finally:

&#x20;       db.close()

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

权限设计：



日志作者可以删除自己的日志

管理员可以删除任何日志

普通用户不能删除他人日志

前端调用

点击删除按钮，确认后发送DELETE请求



需要用户确认避免误删

需要携带Token验证身份

从而实现删除日志功能：首先确认对话框，然后异步删除请求，最后页面刷新

六、用户搜索功能

搜索API接口

接收学号和用户名参数，进行模糊匹配查询



使用contains方法进行模糊匹配

支持多个条件同时搜索

需要返回搜索结果和统计数据

实现功能：



使用SQLAlchemy的contains()方法进行模糊匹配

支持按学号和用户名同时搜索

七、退出登录功能

退出接口

清除Cookie中的Token，使用JavaScript跳转



需要清除客户端存储的Token

需要跳转到登录页

从而提供退出登录功能

前端退出按钮

简单的链接 到退出接口，提供退出入口



八、管理员登陆

管理员专属登录接口

使用admin\_id登录，验证管理员身份，为管理员提供专用登录入口



需要区别于普通用户登录

使用6位数字admin\_id

验证is\_admin=True

九、管理员后台界面

界面布局

创建完整的管理员界面，包含搜索、统计、用户列表、日志列表



需要展示所有功能

需要清晰的布局

需要交互功能

实现的功能：



搜索表单

统计卡片

用户表格

日志表格

删除功能

日志总结

大致完成了管理员后台功能的详细实现后端实现管理员自动分配、专属ID生成、权限验证逻辑，完成用户列表查看、明文密码管理、日志删除、用户搜索、退出登录等接口开发；前端搭建完整管理员后台界面，实现权限控制、数据展示与交互功能。目前管理员专属登录、用户和日志管理、搜索统计等核心功能全部可用，系统管理员模块已具备完整可用的管理能力深入理解了SQLAlchemy会话管理。但是管理员管理功能的查看用户密码的功能还需进一步完善，搜索功能也需要进一步增强

————————————————

版权声明：本文为CSDN博主「Mars\_forever」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。

原文链接：https://blog.csdn.net/2301\_80405405/article/details/160868913

