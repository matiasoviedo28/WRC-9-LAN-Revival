# WRC 9 over LAN without official servers

**English** | [Español](TECNICO.md) · [Back to README](../README.md)

How to play *WRC 9 FIA World Rally Championship* (PC, Steam) multiplayer on a local network, now that the game's online backend no longer works.

| Platform | Status |
| --- | --- |
| Ubuntu + Steam (Snap) + Proton | **Working.** Tested between two PCs over Wi-Fi: the room is visible and you can play. |
| Windows | **Untested.** Ported in `windows/`; see [Windows version](#windows-version-untested). |

Analyzed version: Steam build `6335125`. No game files are modified.

For installation steps, see the [README](../README.md).

## The problem

Multiplayer showed **"you must be connected"**, even with a working internet connection. The game log (`WRC9.log`) said:

```text
profilebase.cpp(313) : warning : Can't login to KtOS. Status 502 Msg
```

KtOS is Kylotonn's backend. On `ktos.kylotonn.com`, nginx still answers, but the API routes the game needs to sign in return `502 Bad Gateway`.

## The solution

Three things are needed. `wrc9-ktos.py` handles the first two.

| Piece | What it does | Why it's needed |
| --- | --- | --- |
| Fake login | Answers locally the requests that went to KtOS | Without a session, the game says "you must be connected" |
| Forced LAN mode | Sets `WRC.UseLanNetwork` to `true` in the game's memory | Without it, the game calls `/multiplayer/connect`, which doesn't exist |
| Open firewall | Lets UDP through between the two PCs | Without it, the search reports that no games were found |

### 1. Fake login

While it runs, the script adds this line to `/etc/hosts`, and removes it on exit:

```text
127.0.0.1 ktos.kylotonn.com # wrc9-ktos
```

It then serves HTTP (80) and HTTPS (443), on `127.0.0.1` only. The game accepts the self-signed certificate because its requests set `WINHTTP_OPTION_SECURITY_FLAGS` to `0x3100`.

Response to `POST /wrc9/prod/users/login`:

```json
{
  "status": 0,
  "status_text": "OK",
  "msg": "",
  "date": 1793508042,
  "data": {
    "user_id": "<hex>",
    "token": "<hex>",
    "req_genkey": "<hex>",
    "new_user": false,
    "token_validity_time": 86400
  }
}
```

Any other route gets `status: 0` and `data: {}`. That was enough for news, challenges and clubs requests.

### 2. Hidden LAN mode

`WRC9.exe` contains a LAN network layer built on RakNet. It seems intended for esports events, since `Common/Settings/LanSettings.cfg` ships with the names `eSportPlayer` and `eSportCopilot`.

The game picks its network layer at `0x140fb6ec0`:

```text
if WRC.UseLanNetwork                  -> LAN layer (0x140fc4980)
else if UseKtOS and UseKtOSMultiplayer -> KtOS layer (0x140fb2120)
else                                  -> Steam layer (0x140fc6090)
```

This option can't be enabled from `UserSettings.cfg`: the game ignores it. So the script writes it to memory while the game starts. Before writing, it checks that the text `UseLanNetwork` is at the expected address; if it doesn't match, it touches nothing.

| Item | RVA (image base `0x140000000`) |
| --- | --- |
| `UseLanNetwork` name | `0x1387f00` |
| Flag value | `0x1a231f0` |

### 3. Room discovery

- The host listens on UDP **60000**.
- The client sends a RakNet ping to `255.255.255.255`, sweeping ports from 60000 upwards.
- The host replies with an `ID_UNCONNECTED_PONG` carrying data such as `WRC9Kylo;1 2;2 1;...`.

Regular ping (ICMP) worked, but the host's firewall was blocking this UDP traffic. To confirm it, we sent the same packet from Python: no reply with `ufw` active, and a reply once it was disabled.

## How we got here

1. There was no known patch or community server, so we analyzed the game.
2. The executable revealed RakNet, `UseLanNetwork` and `LanSettings.cfg`.
3. We added `WRC.UseLanNetwork = true;` and `Engine.UseKtOS = false;` to `UserSettings.cfg`. **It didn't work.**
4. The log showed the KtOS 502, confirmed by querying the API.
5. We rebuilt the login response from the code that parses it and wrote the local server. Login passed, but the error remained.
6. The server log showed `/multiplayer/connect`, proof that the LAN layer wasn't active.
7. We forced the flag in memory. The error went away and we could create a room.
8. Search found nothing: the cause was `ufw` on the host PC.

## Firewall

A permanent rule, instead of disabling `ufw`. Adjust the subnet to your own network:

```bash
sudo ufw allow from 192.168.10.0/24 proto udp
```

This rule wasn't used in our test: there, `ufw` was disabled on the host. If in doubt, open it on the client too.

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| "You must be connected" | Server not running, or started after the game | Close the game, start the script, then the game |
| No `Modo LAN forzado en memoria` | The script didn't detect the game | Make sure it runs with `sudo` |
| `no coincide con este build` | The game was updated | Recalculate the offsets |
| No games found | Host firewall | Check `ufw` and the port with `ss -uanp \| grep :60000` |
| Room still not showing | Wi-Fi isolation or Docker | Try `ping` between PCs, disable "AP isolation" or stop Docker |
| That domain still points to your PC | The line stayed in `/etc/hosts` | Start and close the script, or delete the line marked `# wrc9-ktos` |

## Windows version (untested)

`windows/wrc9-ktos.py` ports the Ubuntu script. `windows/INICIAR.bat` asks for administrator rights and runs it with Python.

| Linux | Windows |
| --- | --- |
| `/etc/hosts` | `C:\Windows\System32\drivers\etc\hosts`, followed by `ipconfig /flushdns` |
| Certificate generated with `openssl` | Bundled `ktos.pem`, self-signed for `ktos.kylotonn.com`. The game doesn't validate it, and it isn't installed in any certificate store. |
| `/proc/<pid>/mem` | `OpenProcess`, `ReadProcessMemory` and `WriteProcessMemory` |
| Fixed base `0x140000000` | Real module base from `CreateToolhelp32Snapshot`, with that base as a fallback |
| Ctrl+C cleans up | Ctrl+C or closing the window cleans up (`SetConsoleCtrlHandler`) |
| `ufw` rule from `iniciar.sh` | Adds the firewall rule `WRC9 LAN` (UDP 60000-60031) once |

The memory write is still validated against `UseLanNetwork` before touching anything. If port 80 is busy, it continues with HTTPS only.

Only the HTTP/HTTPS part was tested, on Linux. The Windows API calls have never run on Windows, and antivirus software may flag the memory write or the `hosts` change.

## Limits and notices

- It only works on the same local network. It doesn't replace online play for clubs, leaderboards or challenges.
- Both players should have the same game build.
- The script runs as root, edits `/etc/hosts` and writes to the memory of `WRC9.exe`. Read it before using it.
- If you share this, share only this document and the script, never game files.
- Login requests include a Steam ticket. The script logs only its size, not its contents.
- The license may restrict this kind of analysis, and reverse engineering rules vary by country. This was done with purchased copies, for private use and without touching the DRM.

## Files

| File | Purpose |
| --- | --- |
| `ubuntu/iniciar.sh` | Ubuntu launcher: checks dependencies, opens UDP 60000-60031 in `ufw` and runs the script |
| `ubuntu/wrc9-ktos.py` | Ubuntu solution: local login and forced LAN mode (tested) |
| `windows/INICIAR.bat` | Windows launcher: asks for admin rights and runs the script |
| `windows/wrc9-ktos.py` | Windows port (untested) |
| `windows/ktos.pem` | Self-signed certificate for the local server |
| `docs/TECNICO.md` | Spanish version of this document |
