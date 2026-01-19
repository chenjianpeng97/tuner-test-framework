# tuner-test-framework

我的测试框架

## 构成

- 用例驱动:pytest
- 浏览器驱动:playwright
- 工具列表
  - excel 处理
  - sql 处理
  - jsonpath 提取
- api 模型管理
- 项目管理 uv

## 第一个 case

- list&export 权限验证并截图
  - sql 工具读取数据库用户列表
  - api 模型管理组件调用 list 和 export 的 api 模型进行 request
  - jsonpath 工具读取 list response 断言
  - excel 工具读取导出文件断言结果
  - 拉取 playwright 进行页面结果截图,复用接口测试期间登录态
