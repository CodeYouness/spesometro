import os

import uvicorn

if __name__ == "__main__":
    # NiceGUI 4.0 solleva ValueError con più worker: sempre 1 (SPEC §7).
    uvicorn.run(
        "spesometro_api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
