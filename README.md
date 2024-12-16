# whiteout survival giftcode bot

a discord bot which utilizes the whiteout survival gift code redemption API to redeem gift codes for a list of users.

# alert

this project has been migrated to [wos-bot](https://github.com/zenpaiang/wos-bot)

# installation and usage

1. clone the repo `git clone https://github.com/zenpaiang/wos-giftcode-bot.git`
2. cd into repo `cd wos-giftcode-bot`
3. install requirements `pip install -r requirements.txt`
4. setup config file (instructions below)
5. run script `python bot.py`

# configuration

after cloning the repo, there will be an example config file (`config.example.json`).  
this file contains three keys:

- `botToken`: your discord bot token
- `playersFile`: location of `players.json`
- `allianceName`: your alliance's 3 letter code (e.g. INF)

`allianceName` is used for autocompletion when removing users from the list.
