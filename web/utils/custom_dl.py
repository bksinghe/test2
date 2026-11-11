"""Stream files out of Telegram's datacentres.

Based on the aiohttp streaming approach used by the original bot (credit:
adarsh-goel), cleaned up and with the unused buffered downloader removed.
"""

from __future__ import annotations

import math

from pyrogram import Client, raw, utils
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session import Auth, Session
from pyrogram.types import Message

from core import state


async def chunk_size(length: int) -> int:
    return 2 ** max(min(math.ceil(math.log2(max(length, 1) / 1024)), 10), 2) * 1024


async def offset_fix(offset: int, chunk: int) -> int:
    return offset - offset % chunk


class TGCustomYield:
    """Yield bytes for a media message stored in the bin channel."""

    def __init__(self) -> None:
        self.main_bot: Client = state.bot

    @staticmethod
    async def generate_file_properties(message: Message) -> FileId:
        media = getattr(message, message.media.value, None)
        file_id = FileId.decode(media.file_id)
        # attributes used by the routes
        file_id.file_size = getattr(media, "file_size", 0)
        file_id.mime_type = getattr(media, "mime_type", "") or ""
        file_id.file_name = getattr(media, "file_name", "") or ""
        return file_id

    async def generate_media_session(self, client: Client, message: Message) -> Session:
        data = await self.generate_file_properties(message)
        session = client.media_sessions.get(data.dc_id)

        if session is not None:
            return session

        if data.dc_id != await client.storage.dc_id():
            session = Session(
                client,
                data.dc_id,
                await Auth(client, data.dc_id, await client.storage.test_mode()).create(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await session.start()

            for _ in range(3):
                exported = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=data.dc_id)
                )
                try:
                    await session.send(
                        raw.functions.auth.ImportAuthorization(
                            id=exported.id, bytes=exported.bytes
                        )
                    )
                except AuthBytesInvalid:
                    continue
                else:
                    break
            else:
                await session.stop()
                raise AuthBytesInvalid
        else:
            session = Session(
                client,
                data.dc_id,
                await client.storage.auth_key(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await session.start()

        client.media_sessions[data.dc_id] = session
        return session

    @staticmethod
    async def get_location(file_id: FileId):
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id, access_hash=file_id.chat_access_hash
                )
            elif file_id.chat_access_hash == 0:
                peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
            else:
                peer = raw.types.InputPeerChannel(
                    channel_id=utils.get_channel_id(file_id.chat_id),
                    access_hash=file_id.chat_access_hash,
                )
            return raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )

        if file_type == FileType.PHOTO:
            return raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )

        return raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size,
        )

    async def yield_file(
        self,
        media_message: Message,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk: int,
    ) -> bytes | None:
        client = self.main_bot
        data = await self.generate_file_properties(media_message)
        media_session = await self.generate_media_session(client, media_message)
        location = await self.get_location(data)

        current_part = 1
        response = await media_session.send(
            raw.functions.upload.GetFile(location=location, offset=offset, limit=chunk)
        )

        if not isinstance(response, raw.types.upload.File):
            return

        while current_part <= part_count:
            payload = response.bytes
            if not payload:
                break
            offset += chunk

            if part_count == 1:
                yield payload[first_part_cut:last_part_cut]
                break
            if current_part == 1:
                yield payload[first_part_cut:]
            elif current_part < part_count:
                yield payload
            else:
                yield payload[:last_part_cut]

            response = await media_session.send(
                raw.functions.upload.GetFile(location=location, offset=offset, limit=chunk)
            )
            if not isinstance(response, raw.types.upload.File):
                break
            current_part += 1


__all__ = ["TGCustomYield", "chunk_size", "offset_fix"]
