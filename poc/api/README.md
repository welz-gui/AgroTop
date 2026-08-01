# API da PoC mobile

Casca FastAPI sobre a autenticação, os repositórios e as regras existentes do AgroTop.
Ela se recusa a atender se `AGROTOP_FORCE_SQLITE=1` não estiver definido.

## Executar no Windows (PowerShell)

Na raiz do repositório:

```powershell
python -m venv C:\tmp\agrotop-api-venv
C:\tmp\agrotop-api-venv\Scripts\python -m pip install -r poc\api\requirements.txt
$env:AGROTOP_FORCE_SQLITE = "1"
$env:AGROTOP_ADMIN_PASSWORD = "troque-esta-senha"
$env:AGROTOP_OP_PASSWORD = "troque-esta-senha"
$env:AGROTOP_API_SECRET = "gere-um-segredo-aleatorio-com-32-ou-mais-caracteres"
C:\tmp\agrotop-api-venv\Scripts\python -c "import database; database.init_db()"
C:\tmp\agrotop-api-venv\Scripts\python -m uvicorn poc.api.main:app --host 0.0.0.0 --port 8000
```

Use `http://10.0.2.2:8000` no emulador Android ou o IP da máquina na rede local em um
aparelho físico. A documentação interativa fica em `http://localhost:8000/docs`.

O token JWT expira em 8 horas. `AGROTOP_API_SECRET` não tem valor padrão e nunca deve ser
commitado. A API mantém a compatibilidade de login do web: PBKDF2-SHA256 e migração do
hash SHA-256 legado quando o login é bem-sucedido.

## Prova de reutilização

- senha: `services.seguranca._verify_password`;
- lista/ficha: `repositories.animais`;
- GMD recente: `repositories.pesagens.calculate_gmd`, o mesmo chamado pelo web;
- GMD total: `services.zootecnia.calculate_gmd_total`, sem fórmula na API ou no Dart.
