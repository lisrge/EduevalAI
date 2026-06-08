山东大学项目实训（一）：项目实训跟踪过程的OpenClaw 开放智能体



前言

经过队内的讨论，我和其他组员对于本次项目已经有了初步的认知和理解，并且确定了组内的分工。我们组的项目是项目实训跟踪过程的OpenClaw开放智能体。我们初步的任务是先接收所有同学的项目实训申请书，通过AI给出自动评分



个人任务

我负责的是基础服务搭建，后端框架基础设施与底层服务开发，为整个系统提供数据持久化支持和配置管理能力。



实现功能：



FastAPI项目启动与自动配置

CORS跨域请求配置

SQLAlchemy数据库连接与Session管理

数据库初始化与表创建

Pydantic Settings环境配置管理

用户模型定义（学号、密码、电子签名）

会话模型定义（Token管理、过期时间）

申报模型定义（文件、状态、文本内容）

评分结果模型定义（创新性、可行性得分）

登录注册Schema数据校验

用户资料Schema数据校验

申报数据Schema数据校验

工作部分

FastAPI项目入口配置

思路使用FastAPI框架搭建后端服务入口，配置CORS跨域资源共享，注册各个业务路由模块。

FastAPI是现代Python Web框架，性能优秀且自带API文档。CORS中间件解决前后端分离架构下的跨域问题，模块化路由便于维护。



该部分实现的功能：



初始化FastAPI应用实例

配置CORS允许跨域请求

注册健康检查、认证、用户、申报、导出路由



from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware



from app.api.routes.auth import router as auth\_router

from app.api.routes.applications import router as applications\_router

from app.api.routes.exports import router as exports\_router

from app.api.routes.health import router as health\_router

from app.api.routes.users import router as users\_router

from app.core.config import get\_settings



settings = get\_settings()

app = FastAPI(title=settings.app\_name)



allow\_all\_origins = settings.cors\_origin\_list == \["\*"]

app.add\_middleware(

&#x20;   CORSMiddleware,

&#x20;   allow\_origins=\["\*"] if allow\_all\_origins else settings.cors\_origin\_list,

&#x20;   allow\_credentials=False if allow\_all\_origins else True,

&#x20;   allow\_methods=\["\*"],

&#x20;   allow\_headers=\["\*"],

)



app.include\_router(health\_router, prefix="/api")

app.include\_router(auth\_router, prefix="/api")

app.include\_router(users\_router, prefix="/api")

app.include\_router(applications\_router, prefix="/api")

app.include\_router(exports\_router, prefix="/api")





@app.get("/")

def root() -> dict\[str, str]:

&#x20;   return {

&#x20;       "name": settings.app\_name,

&#x20;       "env": settings.app\_env,

&#x20;       "status": "running",

&#x20;   }

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

27

28

29

30

31

32

33

34

35

36

37

FastAPI启动时会扫描@app.get等装饰器注册路由。CORSMiddleware拦截所有请求，根据配置添加Access-Control-Allow-Origin等响应头。app.include\_router()将各个模块的子路由合并到主应用，prefix参数统一添加API前缀。get\_settings()单例模式加载环境配置。



环境配置管理

Pydantic Settings是Python标准配置方案，自动类 型转换和验证，计算属性简化路径拼接。

因此，使用Pydantic BaseSettings实现环境配置管理，支持从.env 文件加载配置，提供计算属性生成路径



from pathlib import Path



from pydantic\_settings import BaseSettings, SettingsConfigDict



ENV\_FILE\_PATH = str((Path(\_\_file\_\_).resolve().parents\[2] / ".env"))





class Settings(BaseSettings):

&#x20;   app\_name: str = "EduEval AI Backend"

&#x20;   app\_env: str = "development"

&#x20;   app\_host: str = "0.0.0.0"

&#x20;   app\_port: int = 8001



&#x20;   database\_url: str = "sqlite+pysqlite:///./edueval\_ai.sqlite3"



&#x20;   cors\_origins: str = "\*"



&#x20;   storage\_root: str = "./storage"

&#x20;   preview\_converter\_path: str = "soffice"

&#x20;   model\_provider: str = "openai-compatible"

&#x20;   model\_name: str = "deepseek-chat"

&#x20;   model\_base\_url: str | None = None

&#x20;   model\_api\_key: str | None = None



&#x20;   model\_config = SettingsConfigDict(

&#x20;       env\_file=ENV\_FILE\_PATH,

&#x20;       env\_file\_encoding="utf-8",

&#x20;       extra="ignore",

&#x20;       protected\_namespaces=("settings\_",),

&#x20;   )



&#x20;   @property

&#x20;   def cors\_origin\_list(self) -> list\[str]:

&#x20;       return \[origin.strip() for origin in self.cors\_origins.split(",") if origin.strip()]



&#x20;   @property

&#x20;   def backend\_root(self) -> Path:

&#x20;       return Path(\_\_file\_\_).resolve().parents\[2]



&#x20;   @property

&#x20;   def storage\_path(self) -> Path:

&#x20;       return (self.backend\_root / self.storage\_root).resolve()



&#x20;   @property

&#x20;   def application\_storage\_path(self) -> Path:

&#x20;       return self.storage\_path / "applications"



&#x20;   @property

&#x20;   def export\_storage\_path(self) -> Path:

&#x20;       return self.storage\_path / "exports"



&#x20;   @property

&#x20;   def preview\_storage\_path(self) -> Path:

&#x20;       return self.storage\_path / "previews"





def get\_settings() -> Settings:

&#x20;   return Settings()

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

27

28

29

30

31

32

33

34

35

36

37

38

39

40

41

42

43

44

45

46

47

48

49

50

51

52

53

54

55

56

57

58

Pydantic BaseSettings自动读取ENV\_FILE\_PATH指向的.env文件，model\_config定义解析规则。cors\_origin\_list将逗号分隔的字符串拆分为列表。各个storage\_path属性使用Path对象拼接路径，resolve()转换为绝对路径。get\_settings()返回Settings单例，全局共享配置



该部分代码实现了集中管理应用配置，提供数据库、存储、模型等配置，并且能够自动解析.env文件



实现的功能：

应用名称/环境/端口配置



数据库URL配置（SQLite）

CORS配置解析

存储路径配置（应用文件/导出/预览）

AI模型配置（支持OpenAI兼容接口）

数据库连接配置

SQLAlchemy是Python主流ORM框架，SessionLocal工厂确保每个请求独立的数据库连接，get\_db依赖注入是FastAPI标准用法



reate\_engine()创建数据库引擎，pool\_pre\_ping=True在获取连接前测试连接有效性。Sessionmaker创建会话工厂，autoflush=False禁用自动刷新，autocommit=False手动控制事务。get\_db是FastAPI依赖注入函数，通过yield将Session传递给路由函数，finally确保关闭连接释放资源



rom sqlalchemy import create\_engine

from sqlalchemy.orm import DeclarativeBase, sessionmaker



from app.core.config import get\_settings



settings = get\_settings()

engine = create\_engine(settings.database\_url, pool\_pre\_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)





class Base(DeclarativeBase):

&#x20;   pass





def get\_db():

&#x20;   db = SessionLocal()

&#x20;   try:

&#x20;       yield db

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

创建SQLAlchemy引擎和SessionLocal工厂，定义依赖注入函数get\_db提供数据库会话。



实现的功能：



SQLite数据库连接

连接池配置（pool\_pre\_ping）

Session会话获取

自动关闭连接

数据库初始化

导入所有模型类，调用Base.metadata.create\_all()创建所有表



Base是DeclarativeBase子类，metadata存储所有模型元信息。import模型类确保它们注册到Base.metadata。create\_all()检查数据库中是否存在表，不存在则创建（只创建不修改）。bind=engine指定数据库引擎。



这部分代码的作用：



创建所有数据库表

初始化数据库结构

from app.db.base import Base, engine

from app.models.application import ApplicationRecord, ScoreResult

from app.models.user import User, UserSession





def init\_db() -> None:

&#x20;   Base.metadata.create\_all(bind=engine)





if \_\_name\_\_ == "\_\_main\_\_":

&#x20;   init\_db()

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

SQLAlchemy的create\_all()根据模型类定义自动创建数据库表，只需执行一次。



创建的表：



users表

user\_sessions表

application\_records表

score\_results表

工作总结

在任务开始的初期阶段，我们明确了我们组的任务和分工，并且开始学习如何通过小组分工的形式完成一个整体项目。并且学习到了小组分工对于一个项目完成的重要性，认识到了一个项目必须从实际和需求出发，充分考虑实用性以及客户端需求。这一阶段的主要工作是搭建项目核心基础设施，共完成4个核心部分，分别是：项目入口的配置、环境配置、数据库的连接以及数据库初始化。

————————————————

版权声明：本文为CSDN博主「Mars\_forever」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。

原文链接：https://blog.csdn.net/2301\_80405405/article/details/159897548

