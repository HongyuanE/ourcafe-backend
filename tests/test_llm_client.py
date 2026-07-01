import httpx
import pytest
import respx

from app.llm_client import stream_completion


@pytest.mark.asyncio
@respx.mock
async def test_stream_yields_text_then_usage():
    sse = (
        'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
        'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":40,"completion_tokens":8}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=sse)
    )
    chunks, usage = [], {}
    async for kind, payload in stream_completion(messages=[{"role": "user", "content": "hi"}],
                                                 model="google/gemini-3.1-flash-lite",
                                                 api_key="k", temperature=0.1):
        if kind == "text":
            chunks.append(payload)
        elif kind == "usage":
            usage = payload
    assert "".join(chunks) == "Hi there"
    assert usage == {"prompt_tokens": 40, "completion_tokens": 8}
