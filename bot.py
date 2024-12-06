import interactions as discord
import aiohttp
import asyncio
import hashlib
import certifi
import utils
import json
import time
import ssl
import io

redeemLimits = {"inUse": False, "lastUse": 0}

client = discord.Client(intents=discord.Intents.GUILDS)
    
async def redeem_code(session: aiohttp.ClientSession, code: str, player: dict) -> tuple[bool, str, str]:
    timens = time.time_ns()
    
    login_resp = await session.post(
        url="https://wos-giftcode-api.centurygame.com/api/player",
        data={
            "fid": player["id"],
            "time": timens,
            "sign": hashlib.md5(f"fid={player['id']}&time={timens}tB87#kPtkxqOS2".encode("utf-8")).hexdigest()
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=30
    )
    
    try:
        login_result = await login_resp.json()
    except Exception as _:
        return False, "error", "login error"
    
    if "msg" in login_result:
        if login_result["msg"] != "success":
            return False, "error", "login error"
    else:
        return True, None, "rate limited"
    
    timens = time.time_ns()
    
    redeem_resp = await session.post(
        url="https://wos-giftcode-api.centurygame.com/api/gift_code",
        data={
            "cdk": code,
            "fid": player["id"],
            "time": timens,
            "sign": hashlib.md5(f"cdk={code}&fid={player['id']}&time={timens}tB87#kPtkxqOS2".encode("utf-8")).hexdigest()
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=30
    )
    
    try:
        redeem_result = await redeem_resp.json()
    except Exception as _:
        return False, "error", "unknown error"
    
    if redeem_result["err_code"] == 40014:
        return True, None, "gift code does not exist"
    elif redeem_result["err_code"] == 40007:
        return True, None, "gift code has expired"
    elif redeem_result["err_code"] == 40008:
        return False, "already_claimed", "already claimed"
    elif redeem_result["err_code"] == 20000:
        return False, "successfully_claimed", "successfully claimed"
    else:
        return False, "error", "unknown error"

async def recursive_redeem(message: discord.Message, session: aiohttp.ClientSession, code: str, players: list, counters: dict = {"already_claimed": 0, "successfully_claimed": 0, "error": 0}, recursive_depth: int = 0): # success, counters, result            
    results = {}
    
    for i in range(0, len(players), 20):
        batch = players[i:i + 20]
        
        msg = "redeeming gift code" if recursive_depth == 0 else f"redeeming gift code (retry {recursive_depth})"
        
        await message.edit(content=f"{msg}... ({min(i, len(players))}/{len(players)}) | next update <t:{1 + int(time.time()) + (len(batch) * 3)}:R>")
        
        for player in batch:
            start = time.time()
            
            exit, counter, result = await redeem_code(session, code, player)
            
            if exit:
                await message.edit(content=f"error: {result}")
                return
            else:
                counters[counter] += 1
                results[player["name"]] = result
                
            await asyncio.sleep(max(0, 3 - (time.time() - start)))
                
    remaining_players = [player for player in players if "error" in results[player["name"]]]
    
    if len(remaining_players) == 0:
        msg = (
            f"report: gift code `{code}`\n"
            f"successful: {counters['successfully_claimed']} | "
            f"already claimed: {counters['already_claimed']} | "
            f"retries: {recursive_depth}\n\n"
            f"made with ❤️ by zenpai :D"
        )
        
        await message.edit(content=msg)
        
        await session.close()
        return
                
    await recursive_redeem(
        message=message,
        session=session,
        code=code,
        players=remaining_players,
        counters=counters,
        recursive_depth=recursive_depth + 1,
    )

@discord.slash_command(
    name="redeem",
    description="redeem a gift code",
    options=[
        discord.SlashCommandOption(
            name="code",
            description="the code to redeem",
            required=True,
            type=discord.OptionType.STRING
        )
    ]
)
async def redeem(ctx: discord.SlashContext, code: str):
    if redeemLimits["inUse"]:
        await ctx.send("error: there can only be one instance of this command running at once.")
        return
    
    if redeemLimits["lastUse"] + 60 > time.time():
        await ctx.send("error: this command has a limit of 1 use every 1 minute to comply with WOS's rate limits.")
        return
    
    with open(utils.CONFIG["playersFile"], "r") as f:
        playersObj = json.load(f)
        
    players = [{"id": key, "name": playersObj[key]} for key in playersObj]
    
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where())))
    
    message = await ctx.send("waiting...")
    
    await recursive_redeem(message, session, code, players)
    
    redeemLimits["inUse"] = False
    redeemLimits["lastUse"] = time.time()
    
@discord.slash_command(
    name="add_user",
    description="add a user to the redeem list",
    options=[
        discord.SlashCommandOption(
            name="name",
            description="the user's name",
            required=True,
            type=discord.OptionType.STRING
        ),
        discord.SlashCommandOption(
            name="id",
            description="the user's id",
            required=True,
            type=discord.OptionType.STRING
        )
    ]
)
async def add(ctx: discord.SlashContext, name: str, id: str):    
    if utils.intable(id):
        with open(utils.CONFIG["playersFile"], "r") as f:
            players = json.load(f)
            
        if id in players:
            await ctx.send("error: user already exists in the list")
            return
            
        players[id] = name
        
        with open(utils.CONFIG["playersFile"], "w") as f:
            json.dump(players, f, indent=4)
            
        await ctx.send(f"added user {name} to the list.")
    else:
        await ctx.send("error: invalid user id")
    
@discord.slash_command(
    name="remove_user",
    description="remove a user from the redeem list",
    options=[
        discord.SlashCommandOption(
            name="user",
            description="the user's name",
            required=True,
            type=discord.OptionType.STRING,
            autocomplete=True
        )
    ]
)
async def remove(ctx: discord.SlashContext, user: str):
    with open(utils.CONFIG["playersFile"], "r") as f:
        players = json.load(f)
        
    name = players[user]
    
    del players[user]
            
    with open(utils.CONFIG["playersFile"], "w") as f:
        json.dump(players, f, indent=4)
        
    await ctx.send(f"removed user {name} from the list.")
    
@remove.autocomplete("user")
async def user_autocomplete(ctx: discord.AutocompleteContext):
    name = ctx.input_text
    
    with open(utils.CONFIG["playersFile"], "r") as f:
        players = json.load(f)
        
    for player_id, player_name in players.items():
        if name == player_name:
            await ctx.send(choices=[{"name": player_name, "value": player_id}])
            return
        
    levenshteinValues = [
        (player_id, player_name, utils.levenshtein(name, player_name))
        for player_id, player_name in players.items()
    ]
        
    levenshteinValues.sort(key=lambda x: x[2])
    
    await ctx.send(choices=[{"name": player_name, "value": player_id} for player_id, player_name, _ in levenshteinValues[:10]])
    
@discord.slash_command(
    name="list_users",
    description="list all users"
)
async def list_users(ctx: discord.SlashContext):
    with open(utils.CONFIG["playersFile"], "r") as f:
        players = json.load(f)
        
    players_list = "\n".join([f"{player_id}: {player_name}" for player_id, player_name in players.items()])
    
    fake_file = io.BytesIO(players_list.encode("utf-8"))
    await ctx.send(file=discord.File(fake_file, file_name="users.txt"), filename="users.txt")
    
client.start(utils.CONFIG["botToken"])