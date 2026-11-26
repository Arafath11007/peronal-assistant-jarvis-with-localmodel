# from openai import OpenAI
# from jarvis.config import settings

# client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
# r = client.chat.completions.create(
#     model=settings.fast_model,
#     messages=[{"role": "user", "content": "Say hi in five words."}],
# )

# print(r.choices[0].message.content)import time
import time

from openai import OpenAI
from jarvis.config import settings

client = OpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    timeout=180,
)

t = time.time()
r = client.chat.completions.create(
    model=settings.fast_model,
    messages=[{"role": "user", "content": "Say hi in five words"}],
    max_tokens=512,
)
print(f"{time.time() - t:.1f}s")
print("finish_reason:", r.choices[0].finish_reason)
print(r.choices[0].message)