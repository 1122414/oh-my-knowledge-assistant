SYSTEM_PROMPT = """你是 OMKA，一个个人智能知识助手。

你需要根据用户的兴趣、当前项目、最新技术简报、已收藏知识和候选内容回答问题。

规则：
1. 优先使用提供的上下文回答。
2. 如果上下文不足，请明确说明"不确定"或"当前知识库中没有足够信息"。
3. 不要编造 GitHub 项目、数据、Release 或用户收藏。
4. 回答要简洁、实用，适合飞书聊天阅读。
5. 如果用户问"今天有什么值得关注"，优先参考最新 Digest。
6. 如果用户问"我收藏过什么"，优先参考 Knowledge。
7. 如果用户问"这个方向有哪些候选"，优先参考 Candidate。
8. 可以给出建议动作，但不要替用户做投资建议、法律建议、医疗建议。
9. 输出中文。"""


def build_user_prompt(
    user_message: str,
    interests: str = "",
    projects: str = "",
    recent_messages: str = "",
    digest_items: str = "",
    knowledge_items: str = "",
    candidate_items: str = "",
    memory_items: str = "",
) -> str:
    parts = [f"用户问题：\n{user_message}"]

    if interests:
        parts.append(f"用户兴趣：\n{interests}")

    if projects:
        parts.append(f"当前项目：\n{projects}")

    if memory_items:
        parts.append(f"相关记忆：\n{memory_items}")

    if recent_messages:
        parts.append(f"最近对话：\n{recent_messages}")

    if digest_items:
        parts.append(f"最新简报：\n{digest_items}")

    if knowledge_items:
        parts.append(f"已收藏知识：\n{knowledge_items}")

    if candidate_items:
        parts.append(f"候选内容：\n{candidate_items}")

    return "\n\n".join(parts)
