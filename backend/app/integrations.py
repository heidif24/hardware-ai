import os, httpx, base64
from typing import Any

async def search_components(query: str, limit: int = 8) -> dict[str, Any]:
    # Supplier discovery is intentionally not part of the user-facing production workflow.
    return {
        "query": query,
        "results": [],
        "providers": {},
        "notice": "Supplier search and pricing are outside this application's scope. Use the engineering dossier to contact manufacturers directly after an NDA is signed."
    }

async def generate_product_visual(brief: str, design: dict) -> bytes:
    openai_key = os.getenv("OPENAI_API_KEY")
    replicate_token = os.getenv("REPLICATE_API_TOKEN")
    if not openai_key and not replicate_token:
        raise RuntimeError("Configure OPENAI_API_KEY or REPLICATE_API_TOKEN on the backend to enable product concept renders.")
    prompt = (
        "Photorealistic industrial-design product concept render, studio product photography, "
        "neutral light grey background, three-quarter front view, realistic materials, "
        "subtle technical details, no text, no logo, no watermark. This is a visual concept, "
        "not dimensionally verified CAD. Product brief: " + brief +
        ". Functional modules: " + str([m.get("name") for m in design.get("modules", [])])
    )[:3800]
    async with httpx.AsyncClient(timeout=180) as client:
        if openai_key:
            response = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {openai_key}"},
                json={"model": "gpt-image-1", "prompt": prompt, "size": "1536x1024", "quality": "high", "output_format": "png"}
            )
            response.raise_for_status()
            encoded = response.json().get("data", [{}])[0].get("b64_json")
            if encoded:
                return base64.b64decode(encoded)
            raise RuntimeError("OpenAI image service returned no image data.")
        response = await client.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
            headers={"Authorization": f"Bearer {replicate_token}", "Prefer": "wait"},
            json={"input": {"prompt": prompt, "aspect_ratio": "4:3", "output_format": "png", "num_outputs": 1}}
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "succeeded":
            prediction_id = data.get("id")
            if not prediction_id:
                raise RuntimeError("Image provider did not return a prediction ID.")
            import asyncio
            for _ in range(24):
                await asyncio.sleep(5)
                poll = await client.get(
                    "https://api.replicate.com/v1/predictions/" + prediction_id,
                    headers={"Authorization": f"Bearer {replicate_token}"}
                )
                poll.raise_for_status()
                data = poll.json()
                if data.get("status") in ("succeeded", "failed", "canceled"):
                    break
        if data.get("status") != "succeeded":
            raise RuntimeError("Image provider did not complete: " + str(data.get("error") or data.get("status")))
        output = data.get("output")
        image_url = output[0] if isinstance(output, list) and output else output
        if not image_url:
            raise RuntimeError("Image provider returned no image URL.")
        image = await client.get(image_url)
        image.raise_for_status()
        return image.content
