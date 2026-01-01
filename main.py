import discord
from discord.ext import commands, tasks
import json
import random
from datetime import time
import os

# 設定ファイルの読み込み
def load_config():
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'servers': {}}

def save_config(config):
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_quotes():
    if os.path.exists('quotes.json'):
        with open('quotes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'quotes': []}

def save_quotes(quotes):
    with open('quotes.json', 'w', encoding='utf-8') as f:
        json.dump(quotes, f, ensure_ascii=False, indent=2)

# Intentsの設定
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

config = load_config()
quotes = load_quotes()

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
    """語録を追加"""
    quotes['quotes'].append(quote)
    save_quotes(quotes)
    await ctx.send(f'✅ 語録を追加しました: `{quote}`')

@bot.command(name='remove_quote')
@commands.has_permissions(administrator=True)
async def remove_quote(ctx, *, quote: str):
    """語録を削除"""
    if quote in quotes['quotes']:
        quotes['quotes'].remove(quote)
        save_quotes(quotes)
        await ctx.send(f'✅ 語録を削除しました: `{quote}`')
    else:
        await ctx.send(f'❌ 語録が見つかりませんでした')

@bot.command(name='list_quotes')
async def list_quotes(ctx):
    """語録一覧を表示"""
    if not quotes['quotes']:
        await ctx.send('登録された語録がありません')
        return
    
    embed = discord.Embed(title='語録一覧', color=discord.Color.green())
    for i, quote in enumerate(quotes['quotes'], 1):
        embed.add_field(name=f'{i}', value=quote, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='test_quote')
async def test_quote(ctx):
    """ランダムに語録を投稿（テスト用）"""
    if not quotes['quotes']:
        await ctx.send('語録が登録されていません')
        return
    
    quote = random.choice(quotes['quotes'])
    await ctx.send(quote)

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
    
    await ctx.send(embed=embed)

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
        value='語録を追加',
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
    
    await ctx.send(embed=embed)

@tasks.loop(time=time(hour=12, minute=0))
async def daily_quote():
    """定期的に語録を投稿"""
    if not quotes['quotes']:
        return
    
    for guild_id, server_config in config['servers'].items():
        try:
            guild = bot.get_guild(int(guild_id))
            if not guild:
                continue
            
            if 'quote_channel_id' in server_config:
                channel = guild.get_channel(server_config['quote_channel_id'])
                if channel:
                    quote = random.choice(quotes['quotes'])
                    await channel.send(quote)
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