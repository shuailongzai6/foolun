"""准备本地环境：python3 scripts/setup.py [--demo]。"""

import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="添加开发演示账户和内容")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(root / ".venv")

    def run(*arguments):
        subprocess.run([str(python), *arguments], cwd=root, check=True)

    run("-m", "pip", "install", "-r", "requirements.lock", "-e", ".")
    environment = root / ".env"
    content = environment.read_text(encoding="utf-8") if environment.exists() else (root / ".env.example").read_text(encoding="utf-8")
    for key in ("DJANGO_SECRET_KEY", "EDUCATION_IDENTITY_KEY"):
        pattern = rf"(?m)^(?:export[ \t]+)?{key}[ \t]*=[ \t]*(.*)$"
        match = re.search(pattern, content)
        if match and match[1].strip() not in ("", "''", '\"\"'):
            continue
        assignment = key + "=" + secrets.token_urlsafe(50)
        content = re.sub(pattern, assignment, content) if match else content.rstrip() + "\n" + assignment + "\n"
    descriptor = os.open(environment, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)
    run("manage.py", "migrate", "--noinput")
    run("manage.py", "collectstatic", "--noinput")
    if args.demo:
        run("manage.py", "seed_demo")
    print("\n准备完成。启动：.venv/bin/python manage.py runserver '[::]:8017'")


if __name__ == "__main__":
    main()
