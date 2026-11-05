# WRC 9 LAN Revival

**English** | [Español](LEEME.md)

Play *WRC 9 FIA World Rally Championship* multiplayer with your friends again. The official online servers are down, so the game says **"you must be connected"**. This tool brings back multiplayer on a local network, without changing any game file.

| System | Status |
| --- | --- |
| Ubuntu | ✅ Tested: two PCs created a room, joined and played. |
| Windows | ⚠️ Not tested yet. It should work; please report how it goes. |

![Creating a multiplayer meeting point in WRC 9 without the "you must be connected" error](multiplayer.gif)

## What you need

- WRC 9 from Steam, **updated to the same version on every PC**.
- Everyone on **the same network**, such as the same house or Wi-Fi. For different houses, see [Playing from different houses](#playing-from-different-houses-experimental).
- **Every player** runs this tool on their own PC.

## 1. Download

- **Windows:** download **`WRC9-LAN-Revival.exe`** from [Releases](https://github.com/matiasoviedo28/WRC-9-LAN-Revival/releases/latest). Nothing else is needed.
- **Ubuntu:** press the green **Code** button at the top of this page, then **Download ZIP**. Extract it anywhere, for example on your Desktop.

## 2. Start the tool

The tool's messages are in Spanish. Two of them matter: `KtOS local listo` means "ready", and `Modo LAN forzado en memoria` means "LAN mode is on".

### Ubuntu

1. Close WRC 9.
2. Open the `ubuntu` folder, right-click an empty area and choose **Open in Terminal**.
3. Type this and press Enter:
   ```bash
   bash iniciar.sh
   ```
4. Type your password and press Enter. Nothing appears on screen while you type; that's normal.
5. Wait for `KtOS local listo`. **Leave the window open** while you play.

### Windows

1. Close WRC 9.
2. Double-click **`WRC9-LAN-Revival.exe`**.
3. Choose **Yes** when Windows asks for permission. If it says "Windows protected your PC", choose **More info** and then **Run anyway**.
4. Wait for `KtOS local listo`. **Leave the window open** while you play.

<details>
<summary>Alternative without the .exe (needs Python)</summary>

1. Install Python from [python.org](https://www.python.org/downloads/). In the installer, tick **"Add python.exe to PATH"**.
2. Download the ZIP (step 1, Ubuntu), open the `windows` folder and double-click **`INICIAR.bat`**.
3. Continue from step 3 above.

</details>

## 3. Play

1. Start WRC 9 from Steam as usual. The tool's window must show `Modo LAN forzado en memoria`.
2. **One player** creates the room: **Online multiplayer → Create meeting point** (*Crear punto de encuentro* in the Spanish version).
3. **The others** join it: **Online multiplayer → Search meeting point** (*Buscar punto de encuentro*).
4. When you finish, close the game and then close the tool's window.

Anyone can create the room. Nobody needs to stay online for the others to play.

## Something wrong?

| What you see | What to do |
| --- | --- |
| "You must be connected" | Close the game, start the tool **first**, then the game. |
| `Modo LAN forzado en memoria` never appears | Make sure the tool started with administrator rights (password or "Yes"). |
| `no coincide con este build` | Your game version differs from the supported one. Update WRC 9 in Steam and report it. |
| "No games found" | Usually a firewall. On Ubuntu try `sudo ufw disable` (and `sudo ufw enable` afterwards). Also check that both PCs are on the same Wi-Fi. |
| Windows: "Python is missing" | Only with `INICIAR.bat`: install Python, or use the `.exe` instead. |
| Antivirus warning | The tool edits the `hosts` file and the game's memory, so some antivirus software flags it. You can read exactly what it does in `windows/wrc9-ktos.py`; GitHub builds the `.exe` from that file automatically. |

If something else happens, see [Feedback and contact](#feedback-and-contact).

## Playing from different houses (experimental)

This hasn't been tested. With [ZeroTier](https://www.zerotier.com/), every player joins the same virtual network and the game sees it as a local network. Then follow the steps above as if you were in the same house.

Tailscale won't work for this, because it doesn't carry the broadcast the game uses to find rooms.

## Good to know

- It doesn't bring back online achievements, clubs or leaderboards.
- It doesn't modify game files. While it runs, it redirects the game's login server to your own PC and turns on a LAN mode hidden in the game.
- Never share game files, only this tool.

## Feedback and contact

I want to hear from you **whether it works or not**. Every report helps, especially from Windows, which hasn't been tested yet. If something fails, I'll look for a fix.

- Comment on the [Reddit post](https://www.reddit.com/r/WRCTheGame/comments/1xo7fvn/i_got_wrc_9_multiplayer_working_again_after_the/), or
- Open an [issue on GitHub](https://github.com/matiasoviedo28/WRC-9-LAN-Revival/issues), or
- Email me at **[matiasalbertooviedogonzalez@gmail.com](mailto:matiasalbertooviedogonzalez@gmail.com)**.

Please include:

- Your system: Ubuntu or Windows, and its version.
- Whether you were the host or joined someone else's room.
- What happened, and the message on screen if there was one.
- The `wrc9-ktos.log` file, which appears next to the tool. It doesn't contain passwords or your Steam ticket.

## How does it work?

The full story, from the error to the solution, is in the [technical notes](docs/TECHNICAL.md).
