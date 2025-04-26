# requirement

## 配置文件

```yaml config.yaml
input:
  path: "项目成本.xlsx"  
  sheet:
    source:
      name: "工资"
      columns:
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
    reference:
      name: "工时"
      columns:
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
  splitting_columns:
  - 基本工资
  - 岗位工资
output:
  path: "项目成本拆分.xlsx"
  sheet:
    result:
      name: "工资拆分"
```

## 编程规范

- 编写语言为python，要求按python编程规范编写程序
- 默认从配置文件中读取配置，也可从命令行参数中读取输入文件名和表名、输出文件名和表名
- 检查输入文件，如果无法拆分直接退出，并输出无法拆分的原因
- 编写测试用例，确保拆分逻辑正确
- 文件编码方式采用统一采用UTF8

## 拆分规则

- 以表source为基础，参考表reference进行拆分，拆分结果保存到表result中
- 表result与表source列的名称和顺序完全一致，所有列都通过列名来定位
- input.splitting_columns表示表source需要拆分的列的名称
- input.sheet..columns表示处理过程中可能涉及到的列的名称
- 表source中列employee_id和表reference中列employee_id是左连接关系
  - 如果在表reference中找到了对应的记录，列project_id project_category project_hours内容按列名从表reference中获取
  - 如果在表reference中没有找到对应的记录，列project_id project_category project_hours内容保持不变
  - 以表reference中列project-hours为准按比例进行拆分，表reference中列project_hours不允许为零
  - 未在配置文件input.splitting_columns和input.sheet.source.columns中定义的列内容始终保持不变