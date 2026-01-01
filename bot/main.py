import discord
from discord.ext import commands, tasks
import json
import random
from datetime import time, datetime, timedelta
import os
import tweepy

# 設定ファイルの読み込み
def load_config():
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'servers': {}}

def save_config(config):
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# Intentsの設定
intents = discord.Intents.default()
intents.message_content = True  # これを有効にするにはDeveloper Portalで設定が必要
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

config = load_config()

# Twitter API設定
def setup_twitter_api():
    """Twitter APIクライアントのセットアップ"""
    try:
        # twitter_config.jsonから認証情報を読み込み
        if os.path.exists('twitter_config.json'):
            with open('twitter_config.json', 'r') as f:
                twitter_config = json.load(f)
            
            client = tweepy.Client(
                bearer_token=twitter_config.get('bearer_token'),
                consumer_key=twitter_config.get('api_key'),
                consumer_secret=twitter_config.get('api_secret'),
                access_token=twitter_config.get('access_token'),
                access_token_secret=twitter_config.get('access_token_secret')
            )
            return client
        return None
    except Exception as e:
        print(f"Twitter API setup error: {e}")
        return None

twitter_client = setup_twitter_api()

# Twitter画像キャッシュ
twitter_cache = {
    'かなたーと': {
        'images': [],
        'last_updated': None
    }
}

def get_cached_twitter_images(hashtag, cache_duration_minutes=30):
    """キャッシュされたTwitter画像を取得（有効期限付き）"""
    cache_key = hashtag
    
    if cache_key not in twitter_cache:
        twitter_cache[cache_key] = {'images': [], 'last_updated': None}
    
    cache_data = twitter_cache[cache_key]
    
    # キャッシュが有効かチェック
    if cache_data['last_updated']:
        elapsed = datetime.now() - cache_data['last_updated']
        if elapsed < timedelta(minutes=cache_duration_minutes) and cache_data['images']:
            return cache_data['images'], True  # キャッシュから返す
    
    return [], False  # キャッシュ無効

def update_twitter_cache(hashtag, images):
    """Twitterキャッシュを更新"""
    cache_key = hashtag
    twitter_cache[cache_key] = {
        'images': images,
        'last_updated': datetime.now()
    }

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました')
    print(f'Bot ID: {bot.user.id}')
    daily_quote.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    guild_id = str(message.guild.id)
    
    if guild_id in config['servers']:
        server_config = config['servers'][guild_id]
        
        # 反応ワードのチェック
        if 'triggers' in server_config:
            for trigger in server_config['triggers']:
                if trigger['word'] in message.content:
                    await message.channel.send(trigger['response'])
                    break
        
        # 語録ワードのチェック
        if 'quotes' in server_config and server_config['quotes']:
            for quote in server_config['quotes']:
                # 文字列の場合と辞書の場合の両方に対応
                if isinstance(quote, str):
                    quote_text = quote
                    quote_image = None
                else:
                    quote_text = quote.get('text', '')
                    quote_image = quote.get('image')
                
                # メッセージ内に語録のテキストが含まれているかチェック
                if quote_text and quote_text in message.content:
                    if quote_image:
                        embed = discord.Embed(description=quote_text, color=discord.Color.blue())
                        embed.set_image(url=quote_image)
                        await message.channel.send(embed=embed)
                    else:
                        await message.channel.send(quote_text)
                    break
    
    await bot.process_commands(message)

# 設定コマンド群
@bot.command(name='set_channel')
@commands.has_permissions(administrator=True)
async def set_channel(ctx, channel: discord.TextChannel = None):
    """語録投稿チャンネルを設定"""
    if channel is None:
        channel = ctx.channel
    
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers']:
        config['servers'][guild_id] = {}
    
    config['servers'][guild_id]['quote_channel_id'] = channel.id
    save_config(config)
    
    await ctx.send(f'✅ 語録投稿チャンネルを {channel.mention} に設定しました')

@bot.command(name='add_trigger')
@commands.has_permissions(administrator=True)
async def add_trigger(ctx, word: str, *, response: str):
    """反応ワードを追加"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers']:
        config['servers'][guild_id] = {}
    if 'triggers' not in config['servers'][guild_id]:
        config['servers'][guild_id]['triggers'] = []
    
    config['servers'][guild_id]['triggers'].append({
        'word': word,
        'response': response
    })
    save_config(config)
    
    await ctx.send(f'✅ 反応ワードを追加しました\nワード: `{word}`\n応答: `{response}`')

@bot.command(name='remove_trigger')
@commands.has_permissions(administrator=True)
async def remove_trigger(ctx, word: str):
    """反応ワードを削除"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers'] or 'triggers' not in config['servers'][guild_id]:
        await ctx.send('❌ 設定された反応ワードがありません')
        return
    
    triggers = config['servers'][guild_id]['triggers']
    original_len = len(triggers)
    config['servers'][guild_id]['triggers'] = [t for t in triggers if t['word'] != word]
    
    if len(config['servers'][guild_id]['triggers']) < original_len:
        save_config(config)
        await ctx.send(f'✅ 反応ワード `{word}` を削除しました')
    else:
        await ctx.send(f'❌ 反応ワード `{word}` が見つかりませんでした')

@bot.command(name='list_triggers')
async def list_triggers(ctx):
    """反応ワード一覧を表示"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers'] or 'triggers' not in config['servers'][guild_id]:
        await ctx.send('設定された反応ワードがありません')
        return
    
    triggers = config['servers'][guild_id]['triggers']
    if not triggers:
        await ctx.send('設定された反応ワードがありません')
        return
    
    embed = discord.Embed(title='反応ワード一覧', color=discord.Color.blue())
    for trigger in triggers:
        embed.add_field(
            name=f"ワード: {trigger['word']}", 
            value=f"応答: {trigger['response']}", 
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name='add_quote')
@commands.has_permissions(administrator=True)
async def add_quote(ctx, *, quote: str):
    """語録を追加（このサーバー専用）"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers']:
        config['servers'][guild_id] = {}
    if 'quotes' not in config['servers'][guild_id]:
        config['servers'][guild_id]['quotes'] = []
    
    # 画像が添付されているかチェック
    image_url = None
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
            image_url = attachment.url
    
    quote_data = {
        'text': quote,
        'image': image_url
    }
    
    config['servers'][guild_id]['quotes'].append(quote_data)
    save_config(config)
    
    if image_url:
        await ctx.send(f'✅ 語録（画像付き）を追加しました: `{quote}`')
    else:
        await ctx.send(f'✅ 語録を追加しました: `{quote}`')

@bot.command(name='remove_quote')
@commands.has_permissions(administrator=True)
async def remove_quote(ctx, *, quote: str):
    """語録を削除"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers'] or 'quotes' not in config['servers'][guild_id]:
        await ctx.send('❌ 登録された語録がありません')
        return
    
    quotes = config['servers'][guild_id]['quotes']
    removed = False
    for q in quotes:
        # 文字列の場合と辞書の場合の両方に対応
        q_text = q if isinstance(q, str) else q.get('text', '')
        if q_text == quote:
            config['servers'][guild_id]['quotes'].remove(q)
            removed = True
            break
    
    if removed:
        save_config(config)
        await ctx.send(f'✅ 語録を削除しました: `{quote}`')
    else:
        await ctx.send(f'❌ 語録が見つかりませんでした')

@bot.command(name='list_quotes')
async def list_quotes(ctx):
    """語録一覧を表示"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers'] or 'quotes' not in config['servers'][guild_id]:
        await ctx.send('登録された語録がありません')
        return
    
    quotes = config['servers'][guild_id]['quotes']
    if not quotes:
        await ctx.send('登録された語録がありません')
        return
    
    embed = discord.Embed(title='語録一覧', color=discord.Color.green())
    for i, quote in enumerate(quotes, 1):
        # 文字列の場合と辞書の場合の両方に対応
        if isinstance(quote, str):
            embed.add_field(name=f'{i}', value=quote, inline=False)
        else:
            text = quote.get('text', '')
            has_image = '🖼️' if quote.get('image') else ''
            embed.add_field(name=f'{i} {has_image}', value=text, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='test_quote')
async def test_quote(ctx):
    """ランダムに語録を投稿（テスト用）"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers'] or 'quotes' not in config['servers'][guild_id]:
        await ctx.send('語録が登録されていません')
        return
    
    quotes = config['servers'][guild_id]['quotes']
    if not quotes:
        await ctx.send('語録が登録されていません')
        return
    
    quote = random.choice(quotes)
    
    # 文字列の場合と辞書の場合の両方に対応
    if isinstance(quote, str):
        await ctx.send(quote)
    else:
        text = quote.get('text', '')
        image = quote.get('image')
        
        if image:
            embed = discord.Embed(description=text, color=discord.Color.blue())
            embed.set_image(url=image)
            await ctx.send(embed=embed)
        else:
            await ctx.send(text)

@bot.command(name='show_config')
async def show_config(ctx):
    """現在の設定を表示"""
    guild_id = str(ctx.guild.id)
    if guild_id not in config['servers']:
        await ctx.send('このサーバーの設定がありません')
        return
    
    server_config = config['servers'][guild_id]
    embed = discord.Embed(title='サーバー設定', color=discord.Color.purple())
    
    if 'quote_channel_id' in server_config:
        channel = ctx.guild.get_channel(server_config['quote_channel_id'])
        embed.add_field(
            name='語録投稿チャンネル', 
            value=channel.mention if channel else '未設定', 
            inline=False
        )
    else:
        embed.add_field(name='語録投稿チャンネル', value='未設定', inline=False)
    
    trigger_count = len(server_config.get('triggers', []))
    embed.add_field(name='反応ワード数', value=f'{trigger_count}個', inline=False)
    
    quote_count = len(server_config.get('quotes', []))
    embed.add_field(name='語録数', value=f'{quote_count}個', inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='かなたーと')
async def kanata_art(ctx):
    """#かなたーとのツイートから画像をランダムに取得"""
    if not twitter_client:
        await ctx.send('❌ Twitter APIが設定されていません')
        return
    
    try:
        # キャッシュをチェック
        cached_images, is_cached = get_cached_twitter_images('かなたーと', cache_duration_minutes=30)
        
        if is_cached:
            # キャッシュから返す
            if cached_images:
                selected = random.choice(cached_images)
                
                embed = discord.Embed(
                    description=selected['text'][:200] + ('...' if len(selected['text']) > 200 else ''),
                    color=discord.Color.blue()
                )
                embed.set_image(url=selected['image_url'])
                embed.set_footer(text=f"Tweet ID: {selected['tweet_id']} (キャッシュ)")
                
                await ctx.send(embed=embed)
                return
        
        # キャッシュがない場合はAPIから取得
        await ctx.send('🔍 #かなたーと から画像を検索中...')
        
        # ハッシュタグで検索（画像付きツイートのみ）
        tweets = twitter_client.search_recent_tweets(
            query='#かなたーと has:images -is:retweet',
            max_results=100,
            tweet_fields=['attachments', 'author_id'],
            expansions=['attachments.media_keys'],
            media_fields=['url', 'preview_image_url']
        )
        
        if not tweets.data:
            await ctx.send('❌ #かなたーと の画像付きツイートが見つかりませんでした')
            return
        
        # メディア情報を取得
        media_dict = {}
        if tweets.includes and 'media' in tweets.includes:
            for media in tweets.includes['media']:
                media_dict[media.media_key] = media
        
        # 画像付きツイートを収集
        image_tweets = []
        for tweet in tweets.data:
            if hasattr(tweet, 'attachments') and 'media_keys' in tweet.attachments:
                for media_key in tweet.attachments['media_keys']:
                    if media_key in media_dict:
                        media = media_dict[media_key]
                        if media.type == 'photo':
                            image_tweets.append({
                                'text': tweet.text,
                                'image_url': media.url,
                                'tweet_id': tweet.id
                            })
        
        if not image_tweets:
            await ctx.send('❌ 画像が見つかりませんでした')
            return
        
        # キャッシュを更新
        update_twitter_cache('かなたーと', image_tweets)
        
        # ランダムに1つ選択
        selected = random.choice(image_tweets)
        
        embed = discord.Embed(
            description=selected['text'][:200] + ('...' if len(selected['text']) > 200 else ''),
            color=discord.Color.blue()
        )
        embed.set_image(url=selected['image_url'])
        embed.set_footer(text=f"Tweet ID: {selected['tweet_id']}")
        
        await ctx.send(embed=embed)
        
    except tweepy.TweepyException as e:
        error_msg = str(e)
        if '429' in error_msg:
            await ctx.send('❌ Twitter APIのレート制限に達しました。30分後に再試行してください。')
        else:
            await ctx.send(f'❌ Twitter APIエラー: {error_msg}')
    except Exception as e:
        await ctx.send(f'❌ エラーが発生しました: {str(e)}')
        print(f"Error in kanata_art: {e}")

@bot.command(name='help_bot')
async def help_bot(ctx):
    """ボットのヘルプを表示"""
    embed = discord.Embed(
        title='Botコマンド一覧',
        description='管理者のみ実行可能なコマンドには🔒マークがついています',
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name='🔒 !set_channel [#チャンネル]',
        value='語録を投稿するチャンネルを設定',
        inline=False
    )
    embed.add_field(
        name='🔒 !add_trigger <ワード> <応答>',
        value='反応ワードと応答を追加',
        inline=False
    )
    embed.add_field(
        name='🔒 !remove_trigger <ワード>',
        value='反応ワードを削除',
        inline=False
    )
    embed.add_field(
        name='!list_triggers',
        value='反応ワード一覧を表示',
        inline=False
    )
    embed.add_field(
        name='🔒 !add_quote <語録>',
        value='語録を追加（画像を添付すると画像付きで保存）',
        inline=False
    )
    embed.add_field(
        name='🔒 !remove_quote <語録>',
        value='語録を削除',
        inline=False
    )
    embed.add_field(
        name='!list_quotes',
        value='語録一覧を表示',
        inline=False
    )
    embed.add_field(
        name='!test_quote',
        value='ランダムに語録を投稿（テスト用）',
        inline=False
    )
    embed.add_field(
        name='!show_config',
        value='現在のサーバー設定を表示',
        inline=False
    )
    embed.add_field(
        name='!かなたーと',
        value='#かなたーと から画像をランダムに取得',
        inline=False
    )
    
    await ctx.send(embed=embed)

@tasks.loop(minutes=1)  # テスト用: 1分ごと (本番は time=time(hour=12, minute=0) に戻す)
async def daily_quote():
    """定期的に語録を投稿"""
    for guild_id, server_config in config['servers'].items():
        try:
            guild = bot.get_guild(int(guild_id))
            if not guild:
                continue
            
            # 語録が登録されているかチェック
            if 'quotes' not in server_config or not server_config['quotes']:
                continue
            
            if 'quote_channel_id' in server_config:
                channel = guild.get_channel(server_config['quote_channel_id'])
                if channel:
                    quote = random.choice(server_config['quotes'])
                    
                    # 文字列の場合と辞書の場合の両方に対応
                    if isinstance(quote, str):
                        await channel.send(quote)
                    else:
                        text = quote.get('text', '')
                        image = quote.get('image')
                        
                        if image:
                            embed = discord.Embed(description=text, color=discord.Color.blue())
                            embed.set_image(url=image)
                            await channel.send(embed=embed)
                        else:
                            await channel.send(text)
        except Exception as e:
            print(f"エラー (Server {guild_id}): {e}")

@daily_quote.before_loop
async def before_daily_quote():
    await bot.wait_until_ready()

# エラーハンドリング
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('❌ このコマンドを実行する権限がありません（管理者権限が必要です）')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'❌ 引数が不足しています: `{error.param.name}`')
    else:
        await ctx.send(f'❌ エラーが発生しました: {str(error)}')

# Botの起動
if __name__ == '__main__':
    with open('token.txt', 'r') as f:
        token = f.read().strip()
    bot.run(token)
