import requests
import aiohttp
import asyncio 
import os
import re
import pyperclip
import logging

from yandex_music import Client, Album, Playlist, Track
from yandex_music import ClientAsync
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, APIC, TYER, TPOS
from tkinter.filedialog import askdirectory
from tkinter import Tk
from rich.progress import (
    Progress, BarColumn, DownloadColumn,
    TextColumn, TransferSpeedColumn, TimeRemainingColumn,
)

from ym_robber_async.tracks_func_async import download_track_async
from ym_robber_async.common_func_async import clean_filename, is_empty


logger = logging.getLogger(__name__)


async def get_tracks_from_album__async(client, album_id, max_concurrent=5):
    try:
        album = await client.albums_with_tracks(album_id)
        if not album:
            logger.error(f'Альбом {album.id} не найден')
            return [], None

        tracks = []
        if album.volumes:
            logger.debug(f'Найдено {len(album.volumes)} дисков в альбоме')
            for volume in album.volumes:
                tracks.extend(volume)  # cобираем все треки со всех дисков

            if not tracks:
                logger.warning(f'Треки из {album.title} не были добавлены в список треков')
                return [], None

        logger.info(f'Альбом {album.title} найден. В список добавлены {len(tracks)} треков')
        return tracks, album
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return [], None


async def download_album__async(session, album, track_list, output_dir="./downloads", max_concurrent = 4):
    if not track_list:
        logger.error(f'Список треков пуст')
        return

    album_year = album.year
    album_name = clean_filename(album.title) + str(f' ({album_year})')
    album_output_dir = Path(output_dir) / album_name 
    album_output_dir.mkdir(parents=True, exist_ok=True) 

    results = []
    
    semaphore = asyncio.Semaphore(max_concurrent)

    async def download_file_cover():
        # скачиваем обложку отдельным файлом (ради вайба)
        cover_path = album_output_dir / f'{album_name}.jpg'
        try:
            await album.download_cover_async(cover_path, size='1000x1000')
            if is_empty(cover_path) == False:
                logger.info(f'Файл обложки альбома {album_name} скачался')


        except Exception as e:
            logger.warning(f'Файл обложки альбома {album_name} не был скачан: {e}')

    with Progress(
            TextColumn("[cyan]{task.description}"),
            BarColumn(bar_width=30),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
    
            
            task_ids = {
                track.id: progress.add_task(f"    {track.title[:60]} - {str(track.version)}", total=None)
                for track in track_list
            }
            async def download_one(track, index):
                async with semaphore:
                    task_id = task_ids[track.id]
                    try:
                        _, metadata, bitrate = await download_track_async(session, track, album, str(album_output_dir), progress=progress, task_id=task_id)
                        progress.update(task_id, description=f"[green]  o {track.title[:70]}")
                        # track_version = f" - metadata['version']" if metadata['version'] else '' # уддобнее видеть приписку в  прогресс баре
                        # progress.update(task_id, description=f"[green]  o {track.title[:70]}{track_version} ")
            
                        results.append({
                            "track": track,
                            "metadata": metadata,
                            "bitrate": bitrate,
                            "status": "ok",
                            "error": None,
                        })
                        logger.info(f"OK {track.title}")
                    except Exception as e:
                        progress.update(task_id, description=f"[red]  x {track.title[:50]}")
                        results.append({
                            "track": track,
                            "metadata": None,
                            "bitrate": None,
                            "status": "err",
                            "error": str(e),
                        })
                        logger.error(f"ER {track.title}: {e}")

            tasks = [download_one(t, i) for i, t in enumerate(track_list, start=1)]
            tasks.append(download_file_cover())
            await asyncio.gather(*tasks)

    return results, album_output_dir


