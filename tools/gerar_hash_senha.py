#!/usr/bin/env python
"""Gera o hash de uma senha e o SQL para redefinir o acesso de um usuário.

PARA QUE SERVE
    O AgroTop não tem fluxo de "esqueci minha senha" (não há e-mail configurado).
    Se a senha do administrador for perdida, a recuperação é feita escrevendo
    direto no banco — e este script produz o comando pronto para isso.

    O script NÃO acessa o banco. Ele apenas calcula o hash localmente e imprime
    o SQL para você conferir e executar por conta própria.

COMO USAR
    python tools/gerar_hash_senha.py
    python tools/gerar_hash_senha.py --usuario admin

    Depois: Supabase → SQL Editor → cole o UPDATE exibido → Run.
    (Ou, no SQLite local, use o mesmo UPDATE em qualquer cliente sqlite3.)

SEGURANÇA
    - A senha é digitada sem eco e nunca é gravada em arquivo nem enviada a lugar algum.
    - O hash é PBKDF2-SHA256 com salt aleatório, no mesmo formato que `verify_login` espera.
    - Não deixe o SQL com o hash em histórico de terminal compartilhado.
"""

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera hash de senha e SQL de redefinição.")
    ap.add_argument("--usuario", default="admin",
                    help="username a redefinir (padrão: admin)")
    args = ap.parse_args()

    # Importado aqui para reaproveitar exatamente o mesmo algoritmo do app.
    import database as db

    if sys.stdin.isatty():
        senha = getpass.getpass("Nova senha: ")
        confirma = getpass.getpass("Repita a senha: ")
    else:
        # Sem terminal (pipe/CI): lê da entrada padrão, sem confirmação dupla.
        senha = sys.stdin.readline().rstrip("\n")
        confirma = senha
    if not senha:
        print("Senha vazia — abortado.", file=sys.stderr)
        return 1
    if senha != confirma:
        print("As senhas não coincidem — abortado.", file=sys.stderr)
        return 1
    if len(senha) < 8:
        print("AVISO: senha com menos de 8 caracteres.", file=sys.stderr)

    h = db._hash(senha)
    assert db._verify_password(senha, h), "falha na verificação do hash gerado"

    usuario = args.usuario.replace("'", "''")
    print("\n" + "=" * 72)
    print("Hash gerado (PBKDF2-SHA256, salt aleatório) — verificado com sucesso.")
    print("=" * 72)
    print("\n-- Redefinir a senha de um usuário existente:")
    print(f"UPDATE users SET password_hash = '{h}'\n WHERE username = '{usuario}';")
    print("\n-- Se o usuário nem existir mais, recriar como administrador:")
    print(f"INSERT INTO users (username, password_hash, name, role)\n"
          f"VALUES ('{usuario}', '{h}', 'Administrador', 'admin');")
    print("\n-- Confira antes de sair (deve retornar 1 linha):")
    print(f"SELECT id, username, name, role FROM users WHERE username = '{usuario}';")
    print("\nApós rodar, faça login com a nova senha e apague este SQL do histórico.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
