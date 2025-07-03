import scrapy
from scrapy.crawler import CrawlerProcess
from datetime import datetime
import yaml
import os
import re
# 生成当前时间，格式"2025-06-30"

class NetEaseSongSpider(scrapy.Spider):
    name = "netease_song"
    allowed_domains = ["music.163.com"]
    base_url = "https://music.163.com/song?id="
    playlist_url = "https://music.163.com/playlist?id=13922059591"
    
    def __init__(self):
        self.music_yml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '_data/music.yml')
        self.existing_data = self.load_existing_data()
        self.song_ids = []

    def load_existing_data(self):
        """加载现有的music.yml数据"""
        if os.path.exists(self.music_yml_path):
            try:
                with open(self.music_yml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or []
                return {item.get('id'): item for item in data if item and item.get('id')}
            except Exception as e:
                print(f"Error loading music.yml: {e}")
                return {}
        return {}

    def save_to_yml(self, data):
        """保存数据到music.yml"""
        try:
            # 读取现有数据
            existing_list = []
            if os.path.exists(self.music_yml_path):
                with open(self.music_yml_path, 'r', encoding='utf-8') as f:
                    existing_list = yaml.safe_load(f) or []
            
            # 检查是否已存在该ID的数据
            found = False
            for i, item in enumerate(existing_list):
                if item and item.get('id') == data['id']:
                    existing_list[i] = data
                    found = True
                    break
            
            # 如果不存在，则添加新数据
            if not found:
                existing_list.append(data)
            
            # 写入文件
            with open(self.music_yml_path, 'w', encoding='utf-8') as f:
                yaml.dump(existing_list, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            
            print(f"Data saved to music.yml: {data['title']} by {data['artist']}")
        except Exception as e:
            print(f"Error saving to music.yml: {e}")

    def start_requests(self):
        # 首先访问歌单页面获取歌曲ID列表
        yield scrapy.Request(
            url=self.playlist_url,
            callback=self.parse_playlist,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://music.163.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
            }
        )
    
    def parse_playlist(self, response):
        """解析歌单页面，获取所有歌曲ID"""
        # 添加调试信息
        print(f"Response URL: {response.url}")
        print(f"Response status: {response.status}")
        print(f"Response body length: {len(response.body)}")
        
        # 从表格中提取所有歌曲ID
        song_links = response.xpath('//table[@class="m-table"]/tbody/tr')
        print(f"Found {len(song_links)} table rows")
        
        # 尝试其他可能的选择器
        all_links = response.xpath('//a[contains(@href, "/song?id=")]/@href').getall()
        print(f"Found {len(all_links)} song links in total")
        
        # 如果找不到表格，尝试直接从所有链接中提取ID
        if len(song_links) == 0 and len(all_links) > 0:
            print("No table found, extracting IDs from all links...")
            for link in all_links:
                import re
                match = re.search(r'/song\?id=(\d+)', link)
                if match:
                    song_id = int(match.group(1))
                    if song_id not in self.song_ids:
                        self.song_ids.append(song_id)
                        print(f"Found song ID from direct link: {song_id}")
        else:
            for link in song_links:
                # 从链接中提取歌曲ID
                song_id = link.xpath('.//a[contains(@href, "/song?id=")]/@href').re_first(r'/song\?id=(\d+)')
                if song_id:
                    try:
                        song_id = int(song_id)
                        self.song_ids.append(song_id)
                        print(f"Found song ID: {song_id}")
                    except ValueError:
                        continue
        
        print(f"Found {len(self.song_ids)} songs in playlist")
        
        # 对每首歌进行处理
        for song_id in self.song_ids:
            # 检查是否已存在该ID的数据
            if song_id in self.existing_data:
                print(f"Song ID {song_id} already exists in music.yml, using existing data")
                existing_song = self.existing_data[song_id]
                self.save_to_yml(existing_song)
            else:
                print(f"Song ID {song_id} not found in music.yml, crawling...")
                url = f"{self.base_url}{song_id}"
                yield scrapy.Request(
                    url, 
                    callback=self.parse, 
                    meta={'song_id': song_id},
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Referer': 'https://music.163.com/'
                    }
                )

    def parse(self, response):
        song_id = response.meta['song_id']
        cover_src = response.css('div.u-cover img::attr(src)').get()
        # Extract the song title
        title = response.css('div.tit em::text').get()

        # Extract the artist name
        artist = response.xpath('//p[contains(., "歌手")]/span/a/text()').get()

        # Extract the album name
        album = response.xpath('//p[contains(., "所属专辑")]/a/text()').get()
        album = re.sub(r'[\[\(（].*?[\]\)）]', '', album).strip()
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Print the results
        print(f"Cover URL: {cover_src}")
        print(f"Song Title: {title}")
        print(f"Artist Name: {artist}")
        print(f"Album Name: {album}")

        # 构建要保存的数据，确保所有冒号后面都有空格
        song_data = {
            'id': song_id,
            'url': f"{self.base_url}{song_id}",
            'cover_src': cover_src,
            'title': title,
            'artist': artist,
            'album': album,
            'date': current_date
        }
        
        # 保存到music.yml
        self.save_to_yml(song_data)

        # Also yield for potential pipelines
        yield song_data

if __name__ == '__main__':
    # Run the spider programmatically
    process = CrawlerProcess({
      'LOG_LEVEL': 'ERROR',    # 只看错误
    })
    process.crawl(NetEaseSongSpider)
    process.start()  # the script will block here until the crawling is finished
