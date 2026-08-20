# Contributing to Netools Suite ⚡

Thank you for your interest in contributing to **Netools Suite**! We welcome bug reports, feature requests, documentation improvements, and code contributions.

---

## 🛠️ Development Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Azhar457/Netools.git
   cd Netools
   ```

2. **Create a Virtual Environment & Install Dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   pip install -e .
   ```

3. **Run the Deterministic Verification Gate:**
   ```bash
   ./scripts/verify_all.sh
   ```

---

## 📋 Coding Guidelines

- **Zero Halusinasi / Anti-Fabrication:** Always test code with real sockets and real compiler execution before opening a PR.
- **Layered Architecture:**
  - `netools/adapters/`: Hardware & OS specific operations (`systemd-resolved`, `sing-box`, `9router`, `platform_dns`).
  - `netools/services/`: Pure business logic (`proxy_service`, `dns_service`, `pac_service`).
  - `netools/gui/`: CustomTkinter views and UI elements.
  - `netools/libs/`: Reusable network tools, parsers, and loggers.
  - `netools/cli/`: CLI commands and argument parsing.

---

## 🚀 Pull Request Checklist

- [ ] Code passes `python3 -m compileall -q netools tests *.py`
- [ ] Unit tests added or updated in `tests/`
- [ ] `./scripts/verify_all.sh` exits with code `0`
- [ ] Meaningful commit messages following Conventional Commits (e.g. `feat: ...`, `fix: ...`, `docs: ...`)
