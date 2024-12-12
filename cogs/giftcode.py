import interactions as discord
import hashlib
import aiohttp
import asyncio
import certifi
import json
import time
import ssl

class Giftcode(discord.Extension):
    redeemLimits = {"inUse": False, "lastUse": 0}
    
    async def redeem_code(self, session: aiohttp.ClientSession, code: str, player: dict) -> tuple[bool, str, str]:
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
    
    async def recursive_redeem(self, message: discord.Message, session: aiohttp.ClientSession, code: str, players: list, counters: dict = {"already_claimed": 0, "successfully_claimed": 0, "error": 0}, recursive_depth: int = 0): # success, counters, result            
        results = {}
        
        for i in range(0, len(players), 20):
            batch = players[i:i + 20]
            
            msg = "redeeming gift code" if recursive_depth == 0 else f"redeeming gift code (retry {recursive_depth})"
            
            await message.edit(content=f"{msg}... ({min(i, len(players))}/{len(players)}) | next update <t:{1 + int(time.time()) + (len(batch) * 3)}:R>")
            
            for player in batch:
                start = time.time()
                
                exit, counter, result = await self.redeem_code(session, code, player)
                
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
                    
        await self.recursive_redeem(
            message=message,
            session=session,
            code=code,
            players=remaining_players,
            counters=counters,
            recursive_depth=recursive_depth + 1,
        )
    
    @discord.slash_command(
        name="giftcode",
        description="giftcode-related commands",
        sub_cmd_name="redeem",
        sub_cmd_description="redeem a gift code",
        options=[
            discord.SlashCommandOption(
                name="code",
                description="the code to redeem",
                required=True,
                type=discord.OptionType.STRING
            )
        ]
    )
    async def redeem(self, ctx: discord.SlashContext, code: str):
        if self.redeemLimits["inUse"]:
            await ctx.send("error: there can only be one instance of this command running at once.")
            return
        
        if self.redeemLimits["lastUse"] + 60 > time.time():
            await ctx.send("error: this command has a limit of 1 use every 1 minute to comply with WOS's rate limits.")
            return
        
        with open(self.bot.CONFIG["playersFile"], "r") as f:
            playersObj = json.load(f)
            
        players = [{"id": key, "name": playersObj[key]} for key in playersObj]
        
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where())))
        
        message = await ctx.send("waiting...")
        
        await self.recursive_redeem(message, session, code, players)
        
        self.redeemLimits["inUse"] = False
        self.redeemLimits["lastUse"] = time.time()