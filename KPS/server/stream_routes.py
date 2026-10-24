# KPS/server/stream_routes.py

import re
import os
import secrets
import time
from urllib.parse import quote, unquote

from aiohttp import web

from KPS import __version__, StartTime
from KPS.bot import StreamBot, multi_clients, work_loads
from KPS.server.exceptions import FileNotFound, InvalidHash
from KPS.utils.custom_dl import ByteStreamer
from KPS.utils.logger import logger
from KPS.utils.render_template import render_page
from KPS.utils.time_format import get_readable_time

routes = web.RouteTableDef()

SECURE_HASH_LENGTH = 6
CHUNK_SIZE = 1024 * 1024
MAX_CONCURRENT_PER_CLIENT = 8
RANGE_REGEX = re.compile(r"bytes=(?P<start>\d*)-(?P<end>\d*)")
PATTERN_HASH_FIRST = re.compile(
    rf"^([a-zA-Z0-9_-]{{{SECURE_HASH_LENGTH}}})(\d+)(?:/.*)?$")
PATTERN_ID_FIRST = re.compile(r"^(\d+)(?:/.*)?$")
VALID_HASH_REGEX = re.compile(r'^[a-zA-Z0-9_-]+$')

streamers = {}


def get_streamer(client_id: int) -> ByteStreamer:
    if client_id not in streamers:
        streamers[client_id] = ByteStreamer(multi_clients[client_id])
    return streamers[client_id]


def parse_media_request(path: str, query: dict) -> tuple[int, str]:
    clean_path = unquote(path).strip('/')

    match = PATTERN_HASH_FIRST.match(clean_path)
    if match:
        try:
            message_id = int(match.group(2))
            secure_hash = match.group(1)
            if (len(secure_hash) == SECURE_HASH_LENGTH and
                    VALID_HASH_REGEX.match(secure_hash)):
                return message_id, secure_hash
        except ValueError as e:
            raise InvalidHash(f"Invalid message ID format in path: {e}") from e

    match = PATTERN_ID_FIRST.match(clean_path)
    if match:
        try:
            message_id = int(match.group(1))
            secure_hash = query.get("hash", "").strip()
            if (len(secure_hash) == SECURE_HASH_LENGTH and
                    VALID_HASH_REGEX.match(secure_hash)):
                return message_id, secure_hash
            else:
                raise InvalidHash("Invalid or missing hash in query parameter")
        except ValueError as e:
            raise InvalidHash(f"Invalid message ID format in path: {e}") from e

    raise InvalidHash("Invalid URL structure or missing hash")


def select_optimal_client() -> tuple[int, ByteStreamer]:
    if not work_loads:
        raise web.HTTPInternalServerError(
            text=("No available clients to handle the request. "
                  "Please try again later."))

    available_clients = [
        (cid, load) for cid, load in work_loads.items()
        if load < MAX_CONCURRENT_PER_CLIENT]

    if available_clients:
        client_id = min(available_clients, key=lambda x: x[1])[0]
    else:
        client_id = min(work_loads, key=work_loads.get)

    return client_id, get_streamer(client_id)


def parse_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    if not range_header:
        return 0, file_size - 1

    match = RANGE_REGEX.match(range_header)
    if not match:
        raise web.HTTPBadRequest(text=f"Invalid range header: {range_header}")

    start_str = match.group("start")
    end_str = match.group("end")
    if start_str:
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
    else:
        if not end_str:
            raise web.HTTPBadRequest(text=f"Invalid range header: {range_header}")
        suffix_len = int(end_str)
        if suffix_len <= 0:
            raise web.HTTPRequestRangeNotSatisfiable(headers={"Content-Range": f"bytes */{file_size}"})
        start = max(file_size - suffix_len, 0)
        end = file_size - 1

    if start < 0 or end >= file_size or start > end:
        raise web.HTTPRequestRangeNotSatisfiable(
            headers={"Content-Range": f"bytes */{file_size}"}
        )

    return start, end


# @routes.get("/", allow_head=True)
# async def root_redirect(request):
#     raise web.HTTPFound("https://t.me/AlluTvSerials")


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_file = os.path.join(current_dir, "landing.html")

    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    return web.Response(text=html, content_type="text/html")


@routes.get("/status", allow_head=True)
async def status_endpoint(request):
    uptime = time.time() - StartTime
    total_load = sum(work_loads.values())

    workload_distribution = {str(k): v for k, v in sorted(work_loads.items())}

    return web.json_response({
        "server": {
            "status": "operational",
            "version": __version__,
            "uptime": get_readable_time(uptime)
        },
        "telegram_bot": {
            "username": f"@{StreamBot.username}",
            "active_clients": len(multi_clients)
        },
        "resources": {
            "total_workload": total_load,
            "workload_distribution": workload_distribution

        }
    })


@routes.get(r"/watch/rdxbot-{path:.+}", allow_head=True)
async def media_preview(request: web.Request):
    try:
        path = request.match_info["path"]
        message_id, secure_hash = parse_media_request(path, request.query)

        rendered_page = await render_page(
            message_id, secure_hash, requested_action='stream')
        return web.Response(text=rendered_page, content_type='text/html')

    except (InvalidHash, FileNotFound) as e:
        logger.debug(
            f"Client error in preview: {type(e).__name__} - {e}",
            exc_info=True)
        raise web.HTTPNotFound(text="Resource not found") from e
    except Exception as e:

        error_id = secrets.token_hex(6)
        logger.error(f"Preview error {error_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(
            text=f"Server error occurred: {error_id}") from e


@routes.get(r"/rdxbot-{path:.+}", allow_head=True)
async def media_delivery(request: web.Request):
    """Stream a Telegram file with Range support.

    Add ``?download=1`` to force a browser download.  The response is
    prepared before Telegram chunks are fetched so Heroku receives headers
    quickly and does not raise H12 while waiting for the first media chunk.
    """
    client_id = None
    workload_added = False
    response_prepared = False

    try:
        path = request.match_info["path"]
        message_id, secure_hash = parse_media_request(path, request.query)
        client_id, streamer = select_optimal_client()
        work_loads[client_id] += 1
        workload_added = True

        # Metadata should normally be quick.  Fail cleanly instead of leaving
        # a Heroku request open forever when Telegram is temporarily slow.
        try:
            file_info = await __import__('asyncio').wait_for(
                streamer.get_file_info(message_id), timeout=25
            )
        except __import__('asyncio').TimeoutError as exc:
            raise web.HTTPServiceUnavailable(
                text="Telegram is taking too long to respond. Please retry."
            ) from exc

        if not file_info.get('unique_id'):
            raise FileNotFound("File unique ID not found in info.")
        if file_info['unique_id'][:SECURE_HASH_LENGTH] != secure_hash:
            raise InvalidHash("Provided hash does not match file's unique ID.")

        file_size = int(file_info.get('file_size') or 0)
        if file_size <= 0:
            raise FileNotFound("File size is unavailable.")

        requested_range = request.headers.get("Range", "")
        start, end = parse_range_header(requested_range, file_size)
        content_length = end - start + 1
        is_partial = bool(requested_range)

        mime_type = file_info.get('mime_type') or 'application/octet-stream'
        filename = file_info.get('file_name') or f"file_{message_id}"
        safe_filename = quote(filename.replace('/', '_'))
        force_download = request.query.get("download", "").lower() in {
            "1", "true", "yes", "on"
        }
        disposition = "attachment" if force_download else "inline"

        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(content_length),
            "Content-Disposition": (
                f"{disposition}; filename*=UTF-8''{safe_filename}"
            ),
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        }
        if is_partial:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

        status = 206 if is_partial else 200
        if request.method == 'HEAD':
            return web.Response(status=status, headers=headers)

        response = web.StreamResponse(status=status, headers=headers)
        await response.prepare(request)
        response_prepared = True

        bytes_sent = 0
        bytes_to_skip = start % CHUNK_SIZE
        async for chunk in streamer.stream_file(
                message_id, offset=start, limit=content_length):
            if bytes_to_skip:
                if len(chunk) <= bytes_to_skip:
                    bytes_to_skip -= len(chunk)
                    continue
                chunk = chunk[bytes_to_skip:]
                bytes_to_skip = 0

            remaining = content_length - bytes_sent
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk[:remaining]

            if chunk:
                await response.write(chunk)
                bytes_sent += len(chunk)

            if bytes_sent >= content_length:
                break

        await response.write_eof()
        return response

    except (InvalidHash, FileNotFound) as exc:
        if response_prepared:
            logger.warning("File became unavailable after response started: %s", exc)
            return web.Response()
        raise web.HTTPNotFound(text="Resource not found") from exc
    except web.HTTPException:
        raise
    except (ConnectionResetError, BrokenPipeError, __import__('asyncio').CancelledError):
        logger.debug("Client disconnected during file delivery")
        raise
    except Exception as exc:
        error_id = secrets.token_hex(6)
        logger.error("File delivery error %s: %s", error_id, exc, exc_info=True)
        if response_prepared:
            # Headers/body have already started; a new HTTP error response is
            # impossible, so close the stream gracefully.
            try:
                await response.write_eof()
                return response
            except Exception:
                raise
        raise web.HTTPInternalServerError(
            text=f"File delivery failed: {error_id}"
        ) from exc
    finally:
        if workload_added and client_id is not None:
            work_loads[client_id] = max(0, work_loads[client_id] - 1)
