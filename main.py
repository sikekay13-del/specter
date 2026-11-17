import os
import re
from colorama import Fore, Style, init

from modules.social import SocialModule, SITES
from modules.code import CodeModule
from modules.dork import DorkModule
from modules.mail import EmailModule
from modules.phone import PhoneModule
from modules.reporter import build_dataframe, write_json, write_markdown

init(autoreset=True)
OUT_DIR = "output"


def print_specter_logo():
    logo = r"""
 ____  ____  _____ ____ _____ _____ ____
/ ___||  _ \| ____/ ___|_   _| ____|  _ \
\___ \| |_) |  _|| |     | | |  _| | |_) |
 ___) |  __/| |__| |___  | | | |___|  _ <
|____/|_|   |_____\____| |_| |_____|_| \_\
"""
    print(Fore.GREEN + Style.BRIGHT + logo)
    print(Fore.YELLOW + "  Specter - free OSINT footprint aggregator")
    print(Fore.WHITE + "  Checks public traces of an email, username or phone")
    print(Fore.WHITE + "  number and saves a Markdown + JSON report.")
    print(Fore.RED + "  Only scan targets you own or have permission to scan.\n")


def show_main_menu():
    print(Fore.CYAN + "\n  [1] Email lookup")
    print(Fore.CYAN + "  [2] Username lookup")
    print(Fore.CYAN + "  [3] Phone number lookup")
    print(Fore.CYAN + "  [0] Exit\n")


def display_state(result):
    state = result.get("state", "FOUND" if result.get("found", False) else "NOT FOUND")
    color = {
        "FOUND": Fore.GREEN,
        "NOT FOUND": Fore.YELLOW,
        "COULD NOT CHECK": Fore.RED,
    }.get(state, Fore.WHITE)
    return color + (
        f"[{state}] {result.get('source', 'Unknown source')}: "
        f"{result.get('url') or result.get('detail', '')}"
    )


def run_and_report(modules, target, target_type):
    results = []
    for m in modules:
        if not m.can_run(target_type):
            continue
        print(Fore.CYAN + f"[INFO] Running {m.name} module...")
        try:
            results.extend(m.run(target))
        except Exception as e:
            print(Fore.RED + f"[ERROR] {m.name} module failed: {e}")
            results.append({
                "source": f"{m.name} module",
                "url": "",
                "state": "COULD NOT CHECK",
                "found": False,
                "detail": f"module failed: {type(e).__name__}: {e}",
            })

    for r in results:
        print(display_state(r))

    if not results:
        print(Fore.YELLOW + "[WARN] No results.")
        return

    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        df = build_dataframe(results)
        md = write_markdown(df, target, target_type, OUT_DIR)
        js = write_json(df, target, target_type, OUT_DIR)
    except (OSError, ValueError) as e:
        print(Fore.RED + f"[ERROR] Could not write report: {e}")
        return
    print(Fore.GREEN + f"[DONE] Report: {md}")
    print(Fore.GREEN + f"[DONE] JSON:   {js}")


def email_flow():
    target = input("specter/email> Enter email: ").strip()
    if not re.match(r"^[\w\.\+-]+@[\w\.-]+\.\w+$", target):
        print(Fore.RED + "[!] That doesn't look like an email.")
        return
    print(Fore.YELLOW + (
        "[!] Email is sent to public lookup services (XposedOrNot, GitHub, "
        "DuckDuckGo); only its hash is used for Gravatar. DNS checks send "
        "the domain to Google's public DNS resolver."
    ))
    print(Fore.YELLOW + (
        "[!] Results are partial evidence, not a list of registered accounts. "
        "Continue only if you are comfortable sharing this query."
    ))
    run_and_report([EmailModule(), CodeModule(), DorkModule()], target, "email")


def username_flow():
    names = list(SITES.keys())
    print(Fore.CYAN + "\n  [0] ALL platforms")
    for i, n in enumerate(names, 1):
        print(Fore.CYAN + f"  [{i}] {n}")
    print(Fore.CYAN + "  [b] Back\n")

    choice = input("specter/username> Pick platform: ").strip().lower()
    if choice == "b":
        return
    if choice == "0":
        sites = SITES
    elif choice.isdigit() and 1 <= int(choice) <= len(names):
        sites = {names[int(choice) - 1]: SITES[names[int(choice) - 1]]}
    else:
        print(Fore.RED + "[!] Invalid choice.")
        return

    target = input("specter/username> Enter username: ").strip()
    if not target:
        return

    partial = False
    if set(sites) & SocialModule.PARTIAL_SEARCH_PLATFORMS:
        partial_answer = input(
            "specter/username> Search for matching accounts where public search is supported? [Y/n]: "
        ).strip().lower()
        partial = partial_answer not in {"n", "no"}

    run_and_report([SocialModule(sites=sites, allow_partial=partial), DorkModule()], target, "username")


def phone_flow():
    target = input(
        "specter/phone> Enter number (international format, e.g. +442071838750): "
    ).strip()
    if not target:
        return
    region = None
    if not target.startswith("+"):
        region = input(
            "specter/phone> Number is not international; enter its country/region "
            "code [GH]: "
        ).strip().upper() or "GH"
    print(Fore.YELLOW + (
        "[!] Uses numbering-plan metadata only. It cannot identify a subscriber "
        "or provide a street address; carrier details may be outdated."
    ))
    # Keep phone-number lookups local; do not send the number to a search engine.
    run_and_report([PhoneModule(region=region)], target, "phone")


def main():
    print_specter_logo()
    actions = {"1": email_flow, "2": username_flow, "3": phone_flow}
    try:
        while True:
            show_main_menu()
            choice = input("specter> ").strip()
            if choice == "0":
                print("Bye.")
                break
            action = actions.get(choice)
            if action:
                action()
            else:
                print(Fore.RED + "[!] Pick 1, 2, 3 or 0.")
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")


if __name__ == "__main__":
    main()