from difflib import SequenceMatcher
import interactions as discord
import json
import io

# utilities
    
def intable(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False
    
def match_score(item: str, against: str) -> float:    
    matcher = SequenceMatcher(None)
    
    score = 0
    
    matcher.set_seqs(item, against)
    
    if " " in item:
        wordScore = 0
        
        words = item.split(" ")
        
        againstLower = against.lower()
        
        for word in words:
            if word.lower() in againstLower:
                wordScore += 1
                
        score += wordScore / len(words) * 0.6
        
    score += matcher.ratio() * 0.4
        
    return score

# commands

class Users(discord.Extension):    
    @discord.slash_command(
        name="users",
        description="user-related-commands"
    )
    async def users_cmd(self, ctx: discord.SlashContext):
        pass
    
    @users_cmd.subcommand(
        sub_cmd_name="list",
        sub_cmd_description="list all users in the database"
    )
    async def list_users(self, ctx: discord.SlashContext):
        with open(self.bot.CONFIG["playersFile"], "r") as f:
            players = json.load(f)
            
        players_list = "\n".join([f"{player_id}: [{self.bot.CONFIG['allianceName']}] {player_name}" for player_id, player_name in players.items()])
        
        fake_file = io.BytesIO(players_list.encode("utf-8"))
        await ctx.send(file=discord.File(fake_file, file_name="users.txt"), filename="users.txt")
        
    @users_cmd.subcommand(
        sub_cmd_name="add",
        sub_cmd_description="add a user to the database",
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
    async def add(self, ctx: discord.SlashContext, name: str, id: str):    
        if intable(id):
            with open(self.bot.CONFIG["playersFile"], "r") as f:
                players = json.load(f)
                
            if id in players:
                await ctx.send("error: user already exists in the list")
                return
                
            players[id] = name
            
            with open(self.bot.CONFIG["playersFile"], "w") as f:
                json.dump(players, f, indent=4)
                
            await ctx.send(f"added user {name} to the list.")
        else:
            await ctx.send("error: invalid user id")
            
    @users_cmd.subcommand(
        sub_cmd_name="remove",
        sub_cmd_description="remove a user from the database",
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
    async def remove(self, ctx: discord.SlashContext, user: str):
        with open(self.bot.CONFIG["playersFile"], "r") as f:
            players = json.load(f)
            
        name = players[user]
        
        del players[user]
                
        with open(self.bot.CONFIG["playersFile"], "w") as f:
            json.dump(players, f, indent=4)
            
        await ctx.send(f"removed user {name} from the list.")
    
    @users_cmd.subcommand(
        sub_cmd_name="rename",
        sub_cmd_description="rename a user in the database",
        options=[
            discord.SlashCommandOption(
                name="name",
                description="the user's name",
                required=True,
                type=discord.OptionType.STRING,
                autocomplete=True
            ),
            discord.SlashCommandOption(
                name="new_name",
                description="the user's new username",
                required=True,
                type=discord.OptionType.STRING
            )
        ]
    )
    async def rename(self, ctx: discord.SlashContext, user: str, new_name: str):
        with open(self.bot.CONFIG["playersFile"], "r") as f:
            players = json.load(f)
            
        name = players[user]
        
        players[user] = new_name
                
        with open(self.bot.CONFIG["playersFile"], "w") as f:
            json.dump(players, f, indent=4)
            
        await ctx.send(f"changed {name}'s name to {new_name}.")
        
    @rename.autocomplete("user")
    @remove.autocomplete("user")
    async def user_autocomplete(self, ctx: discord.AutocompleteContext):
        name = ctx.input_text
        
        with open(self.bot.CONFIG["playersFile"], "r") as f:
            players = json.load(f)
            
        if name.startswith(self.bot.CONFIG["allianceName"]):
            name = name.replace(self.bot.CONFIG["allianceName"], "")
            
        results = [(player_id, player_name, match_score(name, player_name)) for player_id, player_name in players.items()]
            
        results.sort(reverse=True, key=lambda x: x[2])
        
        max_score = max(results[:25], key=lambda x: x[2])[2]
        
        best_matches = [match for match in results if match[2] >= max_score * (1 - 0.3)]
        
        await ctx.send(choices=[{"name": f"[{self.bot.CONFIG['allianceName']}] {player_name}", "value": player_id} for player_id, player_name, _ in (best_matches[:25] if len(best_matches) else results[:25])])