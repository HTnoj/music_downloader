import yt_dlp
import sys
from art import tprint
import time
from tqdm import tqdm
import os



    
    # что нужно установить для коректной работы
    # yt-dlp
    # yt-dlp[defaulte]
    # FFmpeg
    # deno (https://docs.deno.com/runtime/getting_started/installation/)
    # 
    #
    #
    #
    #





def progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        print(f'\rСкачивание: {percent} at {speed}', end='')
    elif d['status'] == 'finished':
        print('\n✅ Скачивание завершено, обрабатываю...')

def download_one_track(url):
    print(f"Текущая папка: {os.getcwd()}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': 
        [
            {
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',
            },
            {'key': 'EmbedThumbnail',},

            {'key': 'FFmpegMetadata',}
        ],

        'writethumbnail': True,    
        'embedthumbnail': True,    
        # 'addmetadata': True,       # нет нужды прописывать так как выше есть  {'key': 'FFmpegMetadata',}
        'parsemetadata': ['playlist_index:%(track_number)s'],  
        'outtmpl': '%(playlist_title)s/%(playlist_index)02d - %(title)s.%(ext)s',
        'progress_hook': [progress_hook],
        # 'js_runtimes': {'deno': {}},
        # 'compat_opts': ['no-youtube-js-runtime'],
        'quiet': False,
        'ignoreerrors': True,        
        'nooverwrites': True, 
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    print(f"Текущая папка: {os.getcwd()}")


if __name__ == "__main__":
    tprint ("Music downloader")

    # for i in tqdm(range(0,50), desc="Processing"): time.sleep(0.1)

    

    url = input("Вставте ссылку на видео\n")
    download_one_track(url)
    print(f"\n📁 Файлы сохранены в: {Path.cwd() / 'название_плейлиста'}")