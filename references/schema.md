# 输入数据与运行

使用Python 3和python-docx。在允许安装依赖的本地环境，可运行 `python -m pip install -r requirements.txt`；托管环境遵守宿主依赖规则。脚本自身不安装包。

JSON结构示例（示例内容不是任何真实学生的诊断）：
```json
{
  "student": "示例学生",
  "subject": "数学",
  "teacher": "某老师",
  "lesson_date": "2026-11-08",
  "report_date": "2026-11-10",
  "sections": [
    {
      "heading": "一、学情概况与目标方向",
      "blocks": [
        {"type": "paragraph", "text": "此处填写已经核实的本次学情。"}
      ]
    },
    {
      "heading": "二、学生自评与学习状态",
      "blocks": [
        {"type": "subheading", "text": "（一）学生实际表达的学习困难"},
        {"type": "paragraph", "text": "此处填写有证据的自评与相关建议。"}
      ]
    }
  ]
}
```

正式数据按SKILL.md六节结构补全，以纯文本传入，不带Markdown标题符号。teacher可省略。日期均必填，report_date由Agent按用户时区确定。不要自动填今天为试听日期。subject为物理/数学/英语。生成器不验证事实，由Agent对照证据审核。

运行命令在SKILL.md中。所有命令中的路径都替换为当前环境实际路径，路径有空格时使用正确引号。输出已存在会拒绝覆盖；选择新版本文件名。

复杂数学式按需用Word公式对象补充，不将LaTeX源码直接放入正文。普通反馈尽量用清楚的语言说明方法，不必大段抄题。

版面验证优先使用当前环境已有DOCX渲染工具。如Windows已安装Word，可通过合法的本地文档自动化导出临时PDF；不要关闭用户已打开的文档。LibreOffice可用时遵守宿主限制，使用独立用户配置目录。用PDF渲染器查看每一页；只有文本提取或页数检查不构成视觉验证。缺少宋体/黑体时应提示字体替代情况，不声称字体完全一致。
