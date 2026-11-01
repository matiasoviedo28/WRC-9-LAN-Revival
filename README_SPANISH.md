# WRC 9 en LAN sin servidores oficiales

Cómo jugar multijugador en red local a *WRC 9 FIA World Rally Championship* (PC, Steam), ahora que el backend online del juego no funciona.

| Plataforma | Estado |
| --- | --- |
| Ubuntu + Steam (Snap) + Proton | **Funciona.** Probado entre dos PC por Wi-Fi: la sala se ve y se puede jugar. |
| Windows | **Sin probar.** Plan posible más abajo; `wrc9-ktos.py` no funciona allí sin adaptarlo. |

Versión analizada: Steam build `6335125`. No modifica ningún archivo del juego.

## Inicio rápido (Ubuntu)

Ambas PC deben estar en la misma red, tener el juego con el mismo build y usar `wrc9-ktos.py`.

1. Con WRC 9 cerrado, en **ambas** PC:
   ```bash
   sudo python3 wrc9-ktos.py
   ```
   Esperar a `KtOS local listo` y dejar la terminal abierta.
2. Abrir o ajustar el firewall. Para probar, en ambas:
   ```bash
   sudo ufw disable
   ```
   Al terminar: `sudo ufw enable`. Ver [Firewall](#firewall) para una regla permanente.
3. Abrir WRC 9. La terminal debe mostrar `Modo LAN forzado en memoria`.
4. **Host:** Multijugador online → crear sala.
5. **Cliente:** Multijugador online → buscar partidas.
6. Al terminar, cerrar el juego y apretar **Ctrl+C** en la terminal.

## El problema

El multijugador mostraba **"debes estar conectado"**, incluso con internet. El log del juego (`WRC9.log`) decía:

```text
profilebase.cpp(313) : warning : Can't login to KtOS. Status 502 Msg
```

KtOS es el backend de Kylotonn. En `ktos.kylotonn.com` nginx sigue respondiendo, pero las rutas de la API devuelven `502 Bad Gateway`, y son las que el juego necesita para iniciar sesión.

## La solución

Hacen falta tres cosas. `wrc9-ktos.py` resuelve las dos primeras.

| Pieza | Qué hace | Por qué hace falta |
| --- | --- | --- |
| Login falso | Responde en local a las peticiones que iban a KtOS | Sin sesión, el juego dice "debes estar conectado" |
| Modo LAN forzado | Pone `WRC.UseLanNetwork` en `true` en la memoria del juego | Sin esto, el juego usa `/multiplayer/connect`, que no existe |
| Firewall abierto | Deja pasar UDP entre las dos PC | Sin esto, la búsqueda dice "no se encontraron partidas" |

### 1. Login falso

El script agrega esta línea a `/etc/hosts` mientras corre, y la quita al cerrarse:

```text
127.0.0.1 ktos.kylotonn.com # wrc9-ktos
```

Luego atiende HTTP (80) y HTTPS (443), solo en `127.0.0.1`. El juego acepta el certificado autofirmado porque sus peticiones activan `WINHTTP_OPTION_SECURITY_FLAGS` con `0x3100`.

Respuesta a `POST /wrc9/prod/users/login`:

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

Cualquier otra ruta recibe `status: 0` y `data: {}`. Eso alcanzó para noticias, desafíos y clubes.

### 2. Modo LAN oculto

`WRC9.exe` contiene una capa de red LAN sobre RakNet. Parece pensada para eventos de esports, porque `Common/Settings/LanSettings.cfg` trae los nombres `eSportPlayer` y `eSportCopilot`.

El juego elige la capa de red en `0x140fb6ec0`:

```text
si WRC.UseLanNetwork               -> capa LAN (0x140fc4980)
si no, si UseKtOS y UseKtOSMultiplayer -> capa KtOS (0x140fb2120)
si no                              -> capa Steam (0x140fc6090)
```

Esa opción no se puede activar desde `UserSettings.cfg`: el juego la ignora. Por eso el script la escribe en memoria mientras el juego arranca. Antes de escribir, comprueba que el texto `UseLanNetwork` esté en la dirección esperada; si no coincide, no toca nada.

| Dato | RVA (imagen base `0x140000000`) |
| --- | --- |
| Nombre `UseLanNetwork` | `0x1387f00` |
| Valor del flag | `0x1a231f0` |

### 3. Descubrimiento de salas

- El host escucha en UDP **60000**.
- El cliente envía un ping de RakNet a `255.255.255.255`, barriendo puertos desde el 60000.
- El host contesta un `ID_UNCONNECTED_PONG` con datos como `WRC9Kylo;1 2;2 1;...`.

El ping normal (ICMP) funcionaba, pero el firewall del host bloqueaba este UDP. Para comprobarlo, enviamos el mismo paquete desde Python: no hubo respuesta con `ufw` activo y sí la hubo al desactivarlo.

## Cómo se llegó a esto

1. No había parche ni servidor comunitario conocido, así que se analizó el juego.
2. En el ejecutable aparecieron RakNet, `UseLanNetwork` y `LanSettings.cfg`.
3. Se añadieron `WRC.UseLanNetwork = true;` y `Engine.UseKtOS = false;` a `UserSettings.cfg`. **No funcionó.**
4. El log mostró el 502 de KtOS, confirmado al consultar la API.
5. Se reconstruyó la respuesta del login a partir del código que la procesa, y se creó el servidor local. El login pasó, pero seguía el error.
6. El registro del servidor mostró `/multiplayer/connect`, prueba de que la capa LAN no estaba activa.
7. Se forzó el flag en memoria. El error desapareció y se pudo crear la sala.
8. La búsqueda no encontraba nada: era `ufw` en la PC del host.

## Firewall

Regla permanente, en lugar de desactivar `ufw`. Ajustar la subred a la red propia:

```bash
sudo ufw allow from 192.168.10.0/24 proto udp
```

Esta regla no se usó en la prueba: allí se desactivó `ufw` en el host. Ante cualquier duda, abrirlo también en el cliente.

## Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
| --- | --- | --- |
| "Debes estar conectado" | Servidor apagado, o abierto después del juego | Cerrar el juego, abrir el script y luego el juego |
| Sin `Modo LAN forzado en memoria` | El script no detectó el juego | Confirmar que corra con `sudo` |
| `no coincide con este build` | El juego se actualizó | Recalcular los offsets |
| "No se encontraron partidas" | Firewall del host | Revisar `ufw` y ver el puerto con `ss -uanp \| grep :60000` |
| Sigue sin aparecer | Aislamiento de Wi-Fi o Docker | Probar `ping` entre PC, desactivar "aislamiento de AP" o parar Docker |
| Internet raro para ese dominio | Quedó la línea en `/etc/hosts` | Abrir y cerrar el script, o borrar la línea marcada `# wrc9-ktos` |

## Windows: plan posible (sin probar)

Hay que portar tres partes de `wrc9-ktos.py`. Todos los comandos van en PowerShell como administrador.

**1. Hosts.** Cambiar la ruta a:

```text
C:\Windows\System32\drivers\etc\hosts
```

Algunos antivirus bloquean cambios en este archivo.

**2. Certificado.** El script llama a `openssl`, que Windows no trae. Se puede instalar, o generar `c.pem` y `k.pem` en Linux y copiarlos.

**3. Memoria.** Windows no tiene `/proc/<pid>/mem`. Hay que usar la API de Windows, por ejemplo con `ctypes`:

- Reemplazar `os.geteuid()` por una comprobación de administrador.
- Buscar el proceso `WRC9.exe` y **la base real del módulo**. En Windows puede no ser `0x140000000`, así que hay que leerla con `CreateToolhelp32Snapshot`.
- Con `OpenProcess`, usar `ReadProcessMemory` para validar `UseLanNetwork` en `base + 0x1387f00`.
- Escribir `1` con `WriteProcessMemory` en `base + 0x1a231f0`, repitiendo muy seguido desde el arranque, porque el juego elige la capa de red temprano.

**Firewall:**

```powershell
New-NetFirewallRule -DisplayName "WRC9 LAN" -Direction Inbound -Protocol UDP -LocalPort 60000-60031 -Action Allow
```

**Riesgos:** otros procesos pueden ocupar los puertos 80 o 443, y un antivirus puede marcar la escritura en memoria. Un Windows y un Ubuntu deberían poder jugar juntos, pero no se probó.

## Límites y avisos

- Solo sirve en la misma red local; no reemplaza el online para clubes, rankings ni desafíos.
- Ambos deberían tener el mismo build del juego.
- El script corre como root, modifica `/etc/hosts` y escribe en la memoria de `WRC9.exe`. Conviene leerlo antes de usarlo.
- Si se comparte, compartir solo este documento y el script, nunca archivos del juego.
- Las peticiones de login incluyen un ticket de Steam. El script solo registra su tamaño, no su contenido.
- La licencia puede restringir este tipo de análisis, y las reglas sobre ingeniería inversa varían según el país. Esto se hizo con copias compradas, para uso privado y sin tocar el DRM.

## Archivos

| Archivo | Uso |
| --- | --- |
| `wrc9-ktos.py` | La solución: login local y modo LAN forzado |
| `wrc9-ktos.log` | Registro de peticiones de la última sesión |
| `wrc9-lan.sh` | Obsoleto: fue el primer intento vía `UserSettings.cfg` |
