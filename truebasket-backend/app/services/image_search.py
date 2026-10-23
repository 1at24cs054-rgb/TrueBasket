"""Image discovery and secure retrieval service.

Handles:
1. Candidate product image search.
2. SSRF prevention and URL safety validation.
3. Secure image download, content-type verification, and binary integrity validation.
"""

from datetime import datetime, timezone
import io
import ipaddress
import logging
import socket
from typing import List, Optional, Set, Tuple
import urllib.parse
import httpx
from PIL import Image

from app.schemas import ProductImageCandidate
from app.services.web_search import TavilyError, search_tavily

logger = logging.getLogger("truebasket.services.image_search")

# Security configuration
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB limit


# ==============================================================================
# Security & SSRF Protection
# ==============================================================================

def is_safe_image_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate that a URL is safe to retrieve and does not target internal infrastructure."""
    if not url:
        return False, "URL is empty"

    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

        hostname = (parsed.hostname or "").lower().strip()
        if not hostname:
            return False, "URL lacks a valid hostname."

        # Block localhost, loopback, and local network domains
        blocked_hostnames = {"localhost", "metadata", "instance-data"}
        if hostname in blocked_hostnames or hostname.endswith(".local") or hostname.endswith(".internal"):
            return False, f"Hostname '{hostname}' resolves to an internal or reserved domain."

        # Check for IP address literals
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if ip_obj.is_loopback:
                return False, f"Loopback address '{hostname}' is not permitted."
            if ip_obj.is_link_local:
                return False, f"Link-local / cloud metadata address '{hostname}' is not permitted."
            if ip_obj.is_private:
                return False, f"Private network address '{hostname}' is not permitted."
            if ip_obj.is_reserved:
                return False, f"Reserved IP address '{hostname}' is not permitted."
        except ValueError:
            # Not an IP literal, it's a domain name (standard)
            pass

        return True, None

    except Exception as exc:
        return False, f"Malformed URL: {exc}"


# ==============================================================================
# Secure Image Download & Validation
# ==============================================================================

async def download_and_validate_image_detailed(
    url: str,
    max_size_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = 12.0,
    min_dimension_px: int = 100,
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Safely download external image with security, format, size, and resolution validation.

    Returns:
        (image_bytes, mime_type, rejection_reason)
        On success: (bytes, mime, None)
        On failure: (None, None, rejection_reason)
    """
    is_safe, error_reason = is_safe_image_url(url)
    if not is_safe:
        logger.warning("Blocked unsafe image URL '%s': %s", url, error_reason)
        return None, None, f"unsafe_url: {error_reason}"

    headers = {
        "User-Agent": "TrueBasket-Backend-ImagePerception/1.0",
        "Accept": "image/jpeg,image/png,image/webp,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                logger.warning("Image download failed with HTTP %d for %s", resp.status_code, url)
                return None, None, f"download_failed_http_{resp.status_code}"

            content_type = (resp.headers.get("content-type") or "").lower().split(";")[0].strip()
            if content_type not in ALLOWED_IMAGE_MIMES and not content_type.startswith("image/"):
                logger.warning("Downloaded file from %s has non-image MIME '%s'", url, content_type)
                return None, None, "invalid_format_non_image_mime"

            content = resp.content
            if len(content) == 0:
                logger.warning("Downloaded empty image file from %s", url)
                return None, None, "empty_content"

            if len(content) > max_size_bytes:
                logger.warning("Downloaded image from %s exceeds %d bytes limit", url, max_size_bytes)
                return None, None, "oversized_content"

            # Check binary integrity and resolution with Pillow
            try:
                buf = io.BytesIO(content)
                with Image.open(buf) as img:
                    img.verify()
                    detected_format = (img.format or "JPEG").lower()
                    mime_map = {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
                    normalized_mime = mime_map.get(detected_format, "image/jpeg")
                    # Check resolution
                    width, height = img.size
                    if width < min_dimension_px or height < min_dimension_px:
                        logger.warning("Image from %s rejected for low resolution: %dx%d", url, width, height)
                        return None, None, f"low_resolution_{width}x{height}"
            except Exception as img_err:
                logger.warning("Corrupted or unreadable image binary from %s: %s", url, img_err)
                return None, None, f"corrupted_binary: {img_err}"

            return content, normalized_mime, None

    except (httpx.TimeoutException, httpx.RequestError) as exc:
        logger.warning("Network failure downloading image from %s: %s", url, exc)
        return None, None, f"download_network_failure: {exc}"
    except Exception as exc:
        logger.error("Unexpected error during image retrieval from %s: %s", url, exc)
        return None, None, f"unexpected_error: {exc}"


async def download_and_validate_image(
    url: str,
    max_size_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = 12.0,
) -> Optional[Tuple[bytes, str]]:
    """Safely download external image. Returns (bytes, mime) or None."""
    content, mime, _ = await download_and_validate_image_detailed(
        url=url,
        max_size_bytes=max_size_bytes,
        timeout_seconds=timeout_seconds,
    )
    if content and mime:
        return content, mime
    return None


# ==============================================================================
# Image Search Provider Implementation
# ==============================================================================

async def search_product_images(
    query: str,
    max_results: int = 5,
) -> List[ProductImageCandidate]:
    """Discover candidate product packaging image URLs via search provider.

    Args:
        query: Specific product image query (e.g. 'Kelloggs muesli nutrition label back of pack')
        max_results: Number of images to discover.

    Returns:
        Deduplicated list of ProductImageCandidate instances.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    candidates: List[ProductImageCandidate] = []
    seen_urls: Set[str] = set()

    try:
        # Query search engine with include_images=True
        resp = await search_tavily(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_images=True,
        )

        for img_url in resp.images:
            clean_url = img_url.strip()
            if not clean_url or clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            # Fine-grained heuristic classification of image types
            low_url = clean_url.lower()
            if any(term in low_url for term in ["back", "rear", "reverse", "bop", "side"]):
                img_type = "back_of_pack"
            elif any(term in low_url for term in ["nutrition", "nutritional", "facts", "table", "per_100", "per-100", "calories", "macro"]):
                img_type = "nutrition_panel"
            elif any(term in low_url for term in ["ingredient", "ingredients", "composition", "contains"]):
                img_type = "ingredients_panel"
            elif any(term in low_url for term in ["front", "hero", "fop", "pack-front", "box-front", "main"]):
                img_type = "front_of_pack"
            else:
                img_type = "unknown"

            candidates.append(
                ProductImageCandidate(
                    image_url=clean_url,
                    source_page_url=None,
                    image_type=img_type,
                    retrieval_timestamp=now_iso,
                    is_accessible=True,
                    is_usable_label=False,
                    rejection_reason=None,
                )
            )

    except TavilyError as err:
        logger.warning("Image search failed for query '%s': %s", query, err)
    except Exception as exc:
        logger.error("Unexpected error during product image search: %s", exc)

    return candidates
