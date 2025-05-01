# 需求

## 配置

```yaml config.yaml
input:
  path: "input/项目成本.xlsx"  
  sheet:
    source:
      name: "工资"
      columns:
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
output:
  path: "output/项目成本拆分.xlsx"
  sheet:
    result:
      name: "工资拆分"
```

## 规范

- 编写语言为python，要求按python编程规范编写程序
- 默认从配置文件中读取配置，配置文件路径可通过命令行参数设定
- 文件编码方式统一采用UTF8

## 校验

- 如果输入文件不存在，报错并打印文件名后退出
- 或表source不存在，报错并打印表名后退出

## 规则

- 将表source内容复制到表result，表result的表头、数据和格式与表source相同
