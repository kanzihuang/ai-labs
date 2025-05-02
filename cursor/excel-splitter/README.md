# Excel Splitter

一个用于处理Excel文件的Python工具，可以将源表的内容复制到目标表，保持表头、数据和格式的一致性。

## 功能特点

- 支持从配置文件读取设置
- 保持Excel表格的格式（字体、对齐方式、列宽、行高等）
- 提供完整的单元测试
- 支持UTF-8编码

## 安装

1. 克隆仓库：
```bash
git clone <repository-url>
cd excel-splitter
```

2. 创建并激活虚拟环境：
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

## 配置

在`config.yaml`中配置输入输出设置：

```yaml
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

## 使用方法

1. 准备输入文件：
   - 将源Excel文件放在`input`目录下
   - 确保文件名与配置文件中的`input.path`匹配

2. 运行程序：
```bash
python main.py
```

3. 查看结果：
   - 处理后的文件将保存在`output`目录下
   - 文件名与配置文件中的`output.path`匹配

## 运行测试

```bash
python -m pytest test_main.py -v
```

## 项目结构

```
excel-splitter/
├── input/              # 输入文件目录
├── output/             # 输出文件目录
├── main.py            # 主程序
├── test_main.py       # 单元测试
├── config.yaml        # 配置文件
├── requirements.txt   # 项目依赖
└── README.md         # 项目文档
```

## 依赖

- Python 3.6+
- openpyxl
- pyyaml
- pytest (用于测试)

## 错误处理

- 如果输入文件不存在，程序会报错并退出
- 如果源表不存在，程序会报错并退出
- 所有错误信息都会打印到控制台 