# CLI Tortoises: playable demo

Ride a tortoise around a living island, battle and tame the wild ones, play the Shell Duel card game and
command the Wartles war table. It runs in the browser on a phone or a computer: open the site and press
**Play the demo**. There's nothing to install and no wallet to connect.

- `index.html` is the landing page, and `game.html` is the game.
- Your progress stays in this browser.

This site is built from [tensorrent/CLI--Tortoises](https://github.com/tensorrent/CLI--Tortoises) at
`3d0cb655618f`. That repo holds the source, the tests, the save server and the build:

```sh
cd app && npm install && npm run build:demo
```

The game's own code here is obfuscated; three.js and the other libraries ship as they are.
