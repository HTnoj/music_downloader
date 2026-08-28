from yandex_music import Client
import pyperclip
import os
import re
from pathlib import Path
from art import tprint
import sys
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, APIC
import requests
import shutil

def is_empty(file):
    if (os.path.exists(file) and os.path.getsize(file) == 0):
        return True
    else: return False


def on_code(code):
    print(f'\n Откройте {code.verification_url} и введите код: {code.user_code} (скопирован в буфер обмена)')
    pyperclip.copy(code.user_code) # код в буфер обмена для удобства


def extract_track_id(url):
    '''
    Извлечение id трека из сслыку, которую отправляет пользователь

    Поддерживает:
    - https://music.yandex.ru/album/8602106/track/57273406?utm_source=web&utm_medium=copy_link

    Агрументы:
        url(str): ссылкана трек
    '''
    match = re.search(r'/track/(\d+)', url) # в строке url ищем шаблонную стрроку '/track/(\d+)'
                                            # где (\d+) означает группу из цифр(\d), которую мы хотим найти.
                                            # + означает, что цифр должно быть больше 1. Больше информации в документации re
    if match:
        return match.group(1)

    if re.match(r'^\d+$', url): return url # случай, если пользователь сразу прислал id трека вместо ссылки 

    return None

def extract_collection_id(url):
    '''
    Извлечение id плейлиста или альбома из сслыки, которую отправляет пользователь
    
    Поддерживает:
    - https://music.yandex.ru/users/username/playlists/12345
    - https://music.yandex.ru/album/12345

    Агрументы:
        url(str): ссылкана на плейлист или альбом 
    '''
    # для альбомов
    match = re.search(r'/album/(\d+)', url)         # в строке url ищем шаблонную стрроку '/album/(\d+)'
                                                    # где (\d+) означает группу из цифр(\d), которую мы хотим найти.
                                                    # + означает, что цифр должно быть больше 1. Больше информации в документации re
    if match:
        return {'type': 'album', 'id': match.group(1)}

    # для плейлистов
    match = re.search(r'/playlists/(\d+)', url)     # в строке url ищем шаблонную стрроку '/playlists/(\d+)'
                                                    # где (\d+) означает группу из цифр(\d), которую мы хотим найти.
                                                    # + означает, что цифр должно быть больше 1. Больше информации в документации re
    if match:
        return {'type': 'playlist', 'id': match.group(1)}

    # случай, если пользователь сразу прислал id альбома или плейлиста вместо ссылки 
    if re.match(r'^\d+$', url): return url 
    
    return None

def get_tracks_from_playlist(client, playlist_id):
    '''
    в плейлистах иногда возвращаются объекты short_track, которые содержать только id трека, 
    а иногда объект Track, который содержит все поля трека, нужные для метаданных 
    '''
    try:
        # извлекаем плейлист по его id
        # 
        playlists = client.users_playlists(playlist_id)
        if not playlists:
            return []
        
        # playlists - список разных версий плейлистов, которые создавал пользователь. берем первый
        pleaylist = playlists[0]
        
        tracks = pleaylist.tracks if pleaylist.tracks else pleaylist.fetch_tracks()
    
        track_list = []
        for short_track in tracks:
            # если каждый элемент в tracks уже объект Track то добавляем его track_list
            if hasattr(short_track, 'track') and short_track.track:
                    track_list.append(short_track.track)
            else:
                # eсли это только id, получаем полные данные
                try:
                    track_obj = client.tracks([short_track.id])[0]
                    track_list.append(track_obj)
                except:
                    continue
                        
        return track_list
    except Exception as e:
        print(f"Ошибка при получении плейлиста: {e}")
        return[]

def get_tracks_from_album(client, album_id):
    try:
        album = client.albums_with_tracks(album_id)

        if not album:
            return []

        tracks = []
        if album.volumes:
            for volume in album.volumes:
                tracks.extend(volume)  # cобираем все треки со всех дисков
        return tracks

    except Exception as e:
        print(f"Ошибка при получении альбома: {e}")
        return []

def download_collection(track_list, token, output_dir="./downloads"):
    '''
    Cкачивание альбома или плейлиста по их id из Яндекс Музыки.
    
    Аргументы:
        track_list (obj): список треков
        token (str): OAuth-токен
        output_dir (str): Папка для сохранения
    '''
    if not track_list:
        print("\nСписок треков пуст.")
        return
    
    total = len(track_list)
    print('\n')
    print(f"Найдено треков: {total}")
    print("=" * 50)
    
    success_count = 0
    error_count = 0

    file_of_cover_downloafded = False

    for i, track in enumerate(track_list, start=1):
        print(f"\nТрек {i}/{total}: {track.title}")
        album_name = "Unknown collection"
        if track.albums:
            album_name = f'{track.albums[0].title} ({track.albums[0].year})'

        filename = f'{track.title}.mp3'
        
        track_output_dir = Path(output_dir) / album_name
        track_output_dir.mkdir(parents=True, exist_ok=True) 

        # скачиваем обложку отдельным файлом (ради вайба)
        if file_of_cover_downloafded == False:
                    album = track.albums[0] if track.albums else None
                    cover_path = track_output_dir / f'{album.title}.jpg'
                    album.download_cover(cover_path, size='400x400')
                    print('!!! Файл обложки альбома сохранен')
                    file_of_cover_downloafded = True
        
        try:
            download_track(track.id, token, str(track_output_dir))
            success_count += 1
        except Exception as e:
            print(f"Ошибка при скачивании трека {track.title}: {e}")
            error_count += 1
            continue

    print("\n" + "=" * 50)
    print(f"Успешно скачано {success_count} треков")
    print(f"С ошибками скачано {error_count} треков")
    print("=" * 50)

    





def get_track_metadata(track):
    artist_names = [artist.name for artist in track.artists]
    artists_str = " & ".join(artist_names)  # "Artist1 & Artist2"
    
    album = track.albums[0] if track.albums else None
    album_title = album.title if album else "Unknown Album"
    album_year = album.year if album else None
    
    track_number = None
    track_number = track.albums[0].track_position.index
    #if hasattr(track, 'track_position') and track.track_position:
    #    track_number = album.track_position.index
    #elif hasattr(track, 'meta_data') and hasattr(track.meta_data, 'number'):
    #    track_number = track.meta_data.number

    
    cover_url = None
    if album:
        try:
            cover_url = album.get_cover_url('400x400')
        except Exception:
            if hasattr(album, 'cover_uri') and album.cover_uri:
                cover_url = album.cover_uri.replace('%%', '400x400')

    # допольнительная информация о треке. в ЯМ обычно указывается в названии трека серым цветом  
    # example: Digeridoo Live in Cornwall, 1990
    track_version = track.version
    
    metadata = {
        "title": track.title,
        "version": track_version,
        "artist": artists_str,
        "album": album_title,
        "year": album_year,
        "track_number": track_number,
        "cover_url": cover_url
    }
    # если есть приписка к названию трека -- выводим ее 
    if metadata['version'] is not None:
        print(f'\tНазвение трека: {metadata["title"]} ({metadata["version"]})')
    else: print(f'\tНазвение трека: {metadata["title"]}')

    print(f'\tАртист: {metadata["artist"]}')
    print(f'\tАльбом: {metadata["album"]}')
    print(f'\tГод: {metadata["year"]}')
    print(f'\tНомер трека: {metadata["track_number"]}')
    print(f'\tОбложка: {metadata["cover_url"]}')
    print('\t')

    return metadata

def download_cover(cover_url, save_path):
    response = requests.get(cover_url, timeout=10)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    return False

def add_metadata_to_mp3(file_path, metadata):
    '''Добавляет метаданные в MP3-файл
    Агрументы:
            file_path(any): путь к файлу
            metadata(dict): метаданные файла
    '''
    
    audio = MP3(str(file_path), ID3=ID3)
    
    # если тегов нет — создаём новый контейнер ID3
    if audio.tags is None:
        print("\tСоздаём контейнер для тегов...")
        audio.add_tags()

    # если есть приписка -- добавляем ее в метаданные
    if metadata['version'] is not None:
        audio.tags.add(TIT2(encoding=3,
                            text=metadata['title']+ ' (' + metadata['version'] + ')'
                            ))
    else: audio.tags.add(TIT2(encoding=3, text=metadata['title']))

    audio.tags.add(TPE1(encoding=3, text=metadata['artist']))
    audio.tags.add(TALB(encoding=3, text=metadata['album']))
    
    if metadata.get('year'):
        audio.tags.add(TDRC(encoding=3, text=str(metadata['year'])))
    
    if metadata.get('track_number'):
        audio.tags.add(TRCK(encoding=3, text=str(metadata['track_number'])))
    
    # добавляем обложку
    if metadata.get('cover_url'):
        try:
            response = requests.get(metadata['cover_url'], timeout=10)
            response.raise_for_status()
            #with open('cover.png', 'wb') as f:
                #f.write(response.content)
            if response.status_code == 200:
                mime = response.headers.get("Content-Type","image/jpeg").split(";")[0]
                print(f"\tContent-Type обложки: {mime}")
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime=mime,                        
                        type=3,
                        desc='Cover',
                        data=response.content
                    )
                )
                print('\tОбложка добавлена')
        except Exception as e:
            print(f"\tНе удалось добавить обложку: {e}")
    
    # сохр изменения
    audio.save()
    print("\tМетаданные добавлены")



def download_track(track_id, token, output_dir="./downloads"):
    '''
    Cкачивание трека по его id из Яндекс Музыки.
    
    Аргументы:
        track_id (str): ID трека
        token (str): OAuth-токен
        output_dir (str): Папка для сохранения
    '''

    client = Client(token).init()
    print('\nПолучение информации о треке...')
    track = client.tracks([track_id])[0]
    # album = track.albums[0]
    metadata = get_track_metadata(track) # получаем метаданные трека в словарь

    if metadata['version'] is not None:
        filename = f'{metadata["title"]} ({metadata["version"]}).mp3'   
    else: filename = f'{metadata["title"]}.mp3'                            
    
    output_path = Path(output_dir) 
    output_path.mkdir(parents=True, exist_ok=True)
    
    file_path = output_path / filename
    

    track.download(str(file_path))
    if file_path.exists():
        print(f'Трек скачан: {file_path}')
        print('\n')
    else:
        print(f'Ошибка скачивания трека: {file_path}')
        print('_'*100)

    print("Добавление метаданных в файл...")
    try:
        add_metadata_to_mp3(file_path, metadata)
    except Exception as e:
        print(f"Ошибка при добавлении метаданных: {e}")
        print("\tФайл скачан, но без метаданных")
    
    print(f'Трек сохранён: {file_path}')
    print('_'*100)