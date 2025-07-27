# Forget
A bulk message deletion tool for Discord similar to undiscord, but better.

## Features
- **Save state** You can close Forget and re-open it later and continue where you left off.
- **Archive deleted messages** Forget never deletes cached messages, so you can reconstruct your conversations later!
- **Top to bottom deletion** Forget queries all messages in a channel first, so you can choose whether to start deleting from the top of the channel, or the bottom.
- **Time Estimates** Forget uses the last 20 message deletion times to estimate how long until it's done, so you can plan when to run it.

You can find cached messages in `cache/` within the working directory of the program. They're stored by their channel id in json.