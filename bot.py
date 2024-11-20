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
        players = json.load(f)
        
    status_message = await ctx.send(f"redeeming code... (0/{len(players.keys())} | next update <t:{int(time.time()) + 62}:R>)")

    counters = {
        "already_claimed": 0,
        "successfully_claimed": 0,
        "error": 0
    }
    
    success = []
    results = {}

    batch_size = 20
    players_list = [{"id": key, "name": players[key]} for key in players]
    total_players = len(players_list)

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))) as session:
        for i in range(0, len(players_list), batch_size):
            batch = players_list[i:i + batch_size]
            
            for player in batch:
                apiStart = time.time()  
                
                timens = time.time_ns()

                login_data = {
                    "fid": player["id"],
                    "time": timens,
                    "sign": hashlib.md5(f"fid={player['id']}&time={timens}tB87#kPtkxqOS2".encode("utf-8")).hexdigest()
                }
                
                async with session.post(
                    url="https://wos-giftcode-api.centurygame.com/api/player",
                    data=login_data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    timeout=30
                ) as login_response:
                    login_result = await login_response.json()
                    
                    if "msg" in login_result:
                        if login_result["msg"] != "success":
                            counters["error"] += 1
                    else:
                        await status_message.edit(content="error: rate limited. try again in 60 seconds.")
                        return
                
                timens = time.time_ns()
                redeem_data = {
                    "cdk": code,
                    "fid": player["id"],
                    "time": timens,
                    "sign": hashlib.md5(f"cdk={code}&fid={player['id']}&time={timens}tB87#kPtkxqOS2".encode("utf-8")).hexdigest()
                }
                
                async with session.post(
                    url="https://wos-giftcode-api.centurygame.com/api/gift_code",
                    data=redeem_data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    timeout=30
                ) as redeem_response:
                    redeem_result = await redeem_response.json()
                
                    if redeem_result["err_code"] == 40014:
                        await status_message.edit(content="error: gift code does not exist")
                        return
                    elif redeem_result["err_code"] == 40007:
                        await status_message.edit(content="error: gift code has expired")
                        return
                    elif redeem_result["err_code"] == 40008:
                        counters["already_claimed"] += 1
                        results[player["name"]] = "already claimed"
                    elif redeem_result["err_code"] == 20000:
                        counters["successfully_claimed"] += 1
                        results[player["name"]] = "successfully claimed"
                        success.append(player["name"])
                    else:
                        counters["error"] += 1
                        results[player["name"]] = "error"
                
                await asyncio.sleep(max(0, 3 - (time.time() - apiStart)))
                
            await status_message.edit(content=f"redeeming code... ({min(i + batch_size, total_players)}/{total_players} | next update <t:{int(time.time()) + 62}:R>)")

    msg = (
        f"report: gift code `{code}`\n"
        f"successful: {counters['successfully_claimed']} | "
        f"already claimed: {counters['already_claimed']} | "
        f"errors: {counters['error']}\n\n"
        f"made with ❤️ by zenpai :D"
    )
    
    fakeFile = io.BytesIO("\n".join([f"{player}: {results[player]}" for player in results]).encode("utf-8"))

    await status_message.edit(
        content=msg,
        file=discord.File(fakeFile, file_name="results.txt"),
    )
    
    redeemLimits["inUse"] = False
    redeemLimits["lastUse"] = time.time()
    
@discord.slash_command(
    name="add_user",
    description="add a user to the redeem list",
    options=[
        discord.SlashCommandOption(
            name="id",
            description="the user's id",
            required=True,
            type=discord.OptionType.STRING
        ),
        discord.SlashCommandOption(
            name="name",
            description="the user's name",
            required=True,
            type=discord.OptionType.STRING
        )
    ]
)
async def add(ctx: discord.SlashContext, id: str, name: str):    
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
    
    if not name.startswith(f"[{utils.CONFIG['allianceName']}]"):
        name = f"[{utils.CONFIG['allianceName']}]" + name
        
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