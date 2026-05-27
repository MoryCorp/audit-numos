import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 10.0
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_BACKOFF = 2.0


async def post_audit_event(webhook_url: str, payload: dict) -> bool:
    if not webhook_url:
        return False

    for attempt in range(1, WEBHOOK_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
                response = await client.post(webhook_url, json=payload)
                if 200 <= response.status_code < 300:
                    logger.info(
                        f"Webhook {payload.get('event')} envoye pour audit {payload.get('audit_id')} (HTTP {response.status_code})"
                    )
                    return True
                logger.warning(
                    f"Webhook tentative {attempt}/{WEBHOOK_MAX_RETRIES} renvoie HTTP {response.status_code} pour audit {payload.get('audit_id')}"
                )
        except Exception as e:
            logger.warning(
                f"Webhook tentative {attempt}/{WEBHOOK_MAX_RETRIES} echouee pour audit {payload.get('audit_id')}: {e}"
            )

        if attempt < WEBHOOK_MAX_RETRIES:
            await asyncio.sleep(WEBHOOK_RETRY_BACKOFF * attempt)

    logger.error(f"Webhook abandonne apres {WEBHOOK_MAX_RETRIES} tentatives pour audit {payload.get('audit_id')}")
    return False
