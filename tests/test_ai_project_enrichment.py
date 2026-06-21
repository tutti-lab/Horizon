import asyncio
import json
from unittest.mock import Mock

import httpx

from src.digests.ai_runner import AIDigestRunner, AIProject
from src.models import AIDigestConfig, SourcesConfig


def test_enrich_github_project_uses_repo_api_and_readme():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/bytedance/UI-TARS-desktop":
            return httpx.Response(
                200,
                json={
                    "description": "Open-source multimodal AI agent stack",
                    "topics": ["Artificial Intelligence", "Developer Tools"],
                    "homepage": "https://ui-tars.example.com",
                    "language": "Python",
                },
            )
        if request.url.path == "/repos/bytedance/UI-TARS-desktop/readme":
            return httpx.Response(
                200,
                text="# UI-TARS\n\nUI-TARS is a multimodal AI agent stack for desktop automation.",
            )
        return httpx.Response(404, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    runner = AIDigestRunner(AIDigestConfig(enabled=True, top_n=5), SourcesConfig(), Mock(), client)
    project = AIProject(
        source="github_trending",
        rank=1,
        name="bytedance/UI-TARS-desktop",
        description="",
        url="https://github.com/bytedance/UI-TARS-desktop",
        topics=[],
    )

    asyncio.run(runner._enrich_github_project(project))
    asyncio.run(client.aclose())

    assert "multimodal" in project.description.lower()
    assert "Artificial Intelligence" in project.topics
    assert project.research_context


def test_needs_project_localization_flags_english_summary():
    project = AIProject(
        source="github_trending",
        rank=1,
        name="demo/repo",
        description="",
        url="https://github.com/demo/repo",
        topics=["Artificial Intelligence"],
        summary_zh="This is still English.",
    )

    assert AIDigestRunner._needs_project_localization(project)


def test_needs_project_localization_flags_incomplete_ellipsis_summary():
    project = AIProject(
        source="github_trending",
        rank=1,
        name="demo/repo",
        description="",
        url="https://github.com/demo/repo",
        topics=["Artificial Intelligence"],
        summary_zh="这是一个围绕人工智能的项目…",
    )

    assert AIDigestRunner._needs_project_localization(project)


def test_fallback_project_summary_returns_chinese_without_raw_english_context():
    project = AIProject(
        source="product_hunt",
        rank=1,
        name="Glowix",
        description="",
        url="https://www.producthunt.com/products/glowix",
        topics=["Artificial Intelligence", "Design"],
        category="Design",
        research_context=["Artificial Intelligence - Product Hunt - Artificial intelligence powers products..."],
    )

    summary = AIDigestRunner._fallback_project_summary(project)

    assert "Artificial Intelligence - Product Hunt" not in summary
    assert "围绕" in summary
    assert "关注度较高" in summary


def test_normalize_chinese_project_text_replaces_product_hunt_boilerplate():
    text = "该项目聚焦AI工具，当前最值得关注的是：Artificial Intelligence - Product Hunt - Artificial intelligence powers products。"

    normalized = AIDigestRunner._normalize_chinese_project_text(text, fallback="这是中文兜底。")

    assert "Product Hunt" not in normalized
    assert "人工智能相关方向近期关注度较高" in normalized


def test_normalize_chinese_project_text_rejects_ellipsis():
    normalized = AIDigestRunner._normalize_chinese_project_text(
        "项目定位：近期在 Product Hunt 榜单中 Pro…",
        fallback="围绕 AI 工作流的效率工具，近期榜单关注度较高。",
    )

    assert normalized == "围绕 AI 工作流的效率工具，近期榜单关注度较高。"
    assert "..." not in normalized
    assert "…" not in normalized


def test_fallback_topics_zh_translates_english_repo_tags():
    project = AIProject(
        source="github_trending",
        rank=1,
        name="demo/repo",
        description="",
        url="https://github.com/demo/repo",
        topics=["browser-use", "ai-agents", "coding"],
        category="Agent",
    )

    topics = AIDigestRunner._fallback_topics_zh(project)

    assert "浏览器自动化" in topics
    assert any("智能体" in topic or "人工智能" in topic for topic in topics)


def test_localize_projects_uses_extended_timeout(monkeypatch):
    captured = {}

    class FakeAIClient:
        async def complete(self, **_kwargs):
            return json.dumps(
                {
                    "items": [
                        {
                            "name": "demo/repo",
                            "summary_zh": "具体中文摘要",
                            "capability_cn": "具体能力",
                            "why_cn": "具体看点",
                            "judgment_cn": "具体判断",
                            "category_zh": "开发工具",
                            "topics_zh": ["开发工具"],
                        }
                    ]
                },
                ensure_ascii=False,
            )

    async def fake_wait_for(awaitable, timeout):
        captured["timeout"] = timeout
        return await awaitable

    monkeypatch.setattr("src.digests.ai_runner.asyncio.wait_for", fake_wait_for)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(404)))
    runner = AIDigestRunner(AIDigestConfig(enabled=True, top_n=1), SourcesConfig(), FakeAIClient(), client)
    project = AIProject(
        source="github_trending",
        rank=1,
        name="demo/repo",
        description="A developer tool",
        url="https://github.com/demo/repo",
        topics=["Developer Tools"],
        category="DevTool",
    )

    asyncio.run(runner._localize_projects([project]))
    asyncio.run(client.aclose())

    assert captured["timeout"] >= 90
    assert project.summary_zh == "具体中文摘要"


def test_localize_projects_matches_repo_short_name(monkeypatch):
    class FakeAIClient:
        async def complete(self, **_kwargs):
            return json.dumps(
                {
                    "items": [
                        {
                            "name": "insomnia",
                            "summary_zh": "开源跨平台 API 客户端",
                            "capability_cn": "调试 GraphQL、REST、gRPC API",
                            "why_cn": "支持多协议 API 调试与协作",
                            "judgment_cn": "成熟的 API 开发工具",
                            "category_zh": "开发工具",
                            "topics_zh": ["开发工具"],
                        }
                    ]
                },
                ensure_ascii=False,
            )

    async def fake_wait_for(awaitable, timeout):
        return await awaitable

    monkeypatch.setattr("src.digests.ai_runner.asyncio.wait_for", fake_wait_for)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(404)))
    runner = AIDigestRunner(AIDigestConfig(enabled=True, top_n=1), SourcesConfig(), FakeAIClient(), client)
    project = AIProject(
        source="github_trending",
        rank=8,
        name="Kong/insomnia",
        description="The open-source, cross-platform API client",
        url="https://github.com/Kong/insomnia",
        topics=["api-client"],
        category="DevTool",
    )

    asyncio.run(runner._localize_projects([project]))
    asyncio.run(client.aclose())

    assert project.summary_zh == "开源跨平台 API 客户端"
    assert project.capability_cn == "调试 GraphQL、REST、gRPC API"


def test_localize_projects_prefers_stable_id_over_name(monkeypatch):
    class FakeAIClient:
        async def complete(self, **_kwargs):
            return json.dumps(
                {
                    "items": [
                        {
                            "id": "p0",
                            "name": "wrong-name",
                            "summary_zh": "开源跨平台 API 客户端",
                            "capability_cn": "调试 GraphQL、REST、gRPC API",
                            "why_cn": "支持多协议 API 调试与协作",
                            "judgment_cn": "成熟的 API 开发工具",
                            "category_zh": "开发工具",
                            "topics_zh": ["开发工具"],
                        }
                    ]
                },
                ensure_ascii=False,
            )

    async def fake_wait_for(awaitable, timeout):
        return await awaitable

    monkeypatch.setattr("src.digests.ai_runner.asyncio.wait_for", fake_wait_for)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(404)))
    runner = AIDigestRunner(AIDigestConfig(enabled=True, top_n=1), SourcesConfig(), FakeAIClient(), client)
    project = AIProject(
        source="github_trending",
        rank=8,
        name="Kong/insomnia",
        description="The open-source, cross-platform API client",
        url="https://github.com/Kong/insomnia",
        topics=["api-client"],
        category="DevTool",
    )

    asyncio.run(runner._localize_projects([project]))
    asyncio.run(client.aclose())

    assert project.summary_zh == "开源跨平台 API 客户端"
    assert project.capability_cn == "调试 GraphQL、REST、gRPC API"


def test_group_block_does_not_truncate_project_summary_with_ellipsis():
    project = AIProject(
        source="github_trending",
        rank=8,
        name="Kong/insomnia",
        description="",
        url="https://github.com/Kong/insomnia",
        topics=["api-client"],
        category="DevTool",
        summary_zh="开源跨平台API客户端，支持GraphQL、REST、WebSockets、SSE和gRPC，提供云端、本地和Git存储",
        capability_cn="多协议API测试、云端本地存储、Git集成",
        why_cn="开发者必备的API调试工具",
        judgment_cn="API开发测试的标准工具",
    )

    block = project.to_group_block(1)

    assert "..." not in block
    assert "…" not in block
    assert "gRPC，提供云端、本地和Git存储" in block


def test_localize_projects_splits_large_batches(monkeypatch):
    captured_timeouts = []

    class FakeAIClient:
        async def complete(self, **_kwargs):
            return json.dumps(
                {
                    "items": [
                        {
                            "name": f"demo/repo-{index}",
                            "summary_zh": f"具体中文摘要 {index}",
                            "capability_cn": "具体能力",
                            "why_cn": "具体看点",
                            "judgment_cn": "具体判断",
                            "category_zh": "开发工具",
                            "topics_zh": ["开发工具"],
                        }
                        for index in range(5)
                    ]
                },
                ensure_ascii=False,
            )

    async def fake_wait_for(awaitable, timeout):
        captured_timeouts.append(timeout)
        return await awaitable

    monkeypatch.setattr("src.digests.ai_runner.asyncio.wait_for", fake_wait_for)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(404)))
    runner = AIDigestRunner(AIDigestConfig(enabled=True, top_n=5), SourcesConfig(), FakeAIClient(), client)
    projects = [
        AIProject(
            source="github_trending",
            rank=index + 1,
            name=f"demo/repo-{index}",
            description="A developer tool",
            url=f"https://github.com/demo/repo-{index}",
            topics=["Developer Tools"],
            category="DevTool",
        )
        for index in range(5)
    ]

    asyncio.run(runner._localize_projects(projects))
    asyncio.run(client.aclose())

    assert len(captured_timeouts) == 2
    assert projects[4].summary_zh == "具体中文摘要 4"
