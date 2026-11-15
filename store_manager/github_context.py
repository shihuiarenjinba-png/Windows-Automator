from __future__ import annotations
import base64, json, urllib.request
SAFE=("README.md","README","docs/STORE.md","docs/PRIVACY.md","docs/README.md","Package.appxmanifest","appxmanifest.xml")

def fetch_context(repo,token,ref="",api_base="https://api.github.com",timeout=30):
    chunks=[]
    for path in SAFE:
        url=f"{api_base}/repos/{repo}/contents/{path}"+(f"?ref={ref}" if ref else "")
        req=urllib.request.Request(url,headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"windows-automator"})
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r: data=json.loads(r.read().decode())
        except Exception: continue
        if data.get("encoding")!="base64" or not data.get("content"): continue
        raw=base64.b64decode(data["content"])
        chunks.append(f"\n--- {path} ---\n"+raw[:200000].decode("utf-8",errors="replace"))
    return "".join(chunks)
