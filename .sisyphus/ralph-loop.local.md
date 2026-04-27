---
active: true
iteration: 1
max_iterations: 500
completion_promise: "VERIFIED"
initial_completion_promise: "DONE"
verification_attempt_id: "0c9f58ce-e2cb-4ceb-aee1-9c89e2413563"
verification_session_id: "ses_2325d9170ffeGtYcBNl1vmKXNW"
started_at: "2026-04-27T06:09:21.840Z"
session_id: "ses_23295a533ffe7PJkxfsAV46lR2"
ultrawork: true
verification_pending: true
strategy: "continue"
message_count_at_start: 4
---
现在开始执行这个mvp_plan
1.环境变量都写入.env中，包括模型相关、常量相关，方便后续进行更改
2.要有全局观，注意后续能扩展重构
3.每写完一个阶段的代码进行一次commit，注意只本地commit不要push到远程，注意使用中文commit信息，并且规范提交
4.注意写完项目之后要告诉我如何进行调试测试项目完成情况，再补一个功能测试脚本
5.严格按照全局AGENTS.md中行为准则去写项目
