import asyncio
from yandex_music import ClientAsync


async def main():
    client = ClientAsync()
    await client.init()
    track = (await client.tracks(['352333']))[0]
    print(track.title)
    

 


    

if __name__ == "__main__":
    asyncio.run(main())